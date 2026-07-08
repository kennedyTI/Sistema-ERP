"""Monta chamados de suprimentos sem conhecer detalhes HTTP do GLPI."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.modules.integracoes.glpi.config import GlpiSettings, get_glpi_settings
from backend.app.modules.integracoes.glpi.schemas.abertura_chamado_schema import (
    AbrirChamadoGlpiRequest,
    ResultadoAberturaGlpi,
)
from backend.app.modules.integracoes.glpi.services.abertura_chamado_service import (
    abrir_chamado_glpi,
    registrar_bloqueio_glpi,
)
from backend.app.modules.printers.machines.models import PrinterMachine
from backend.app.modules.printers.monitoring.alerts.models import AlertaImpressora
from backend.app.modules.printers.monitoring.state.models import PrinterAlertRule
from backend.app.modules.printers.supplies.models import PrinterSupply
from backend.app.modules.printers.supplies.services import (
    SupplyColorNotIdentifiedError,
    SupplyNotFoundError,
    get_cylinder_supply,
    resolve_toner_supply,
)


SUPPORTED_ALERT_CODES = {"replace_toner", "replace_drum"}
EVENT_BY_ALERT_CODE = {
    "replace_toner": "substituir_toner",
    "replace_drum": "substituir_cilindro",
}
EVENT_LABEL = {
    "substituir_toner": "Substituir toner",
    "substituir_cilindro": "Substituir cilindro",
}


def _supply_label(supply: PrinterSupply | None, event_type: str) -> str:
    if supply is None:
        return "TONER" if event_type == "substituir_toner" else "CILINDRO"
    return " ".join(value for value in (supply.suprimento, supply.cor) if value)


def _deduplication_hash(
    machine_id: int,
    event_type: str,
    supply: PrinterSupply | None,
) -> str:
    base = f"impressoras:maquina:{machine_id}:{event_type}"
    if event_type == "substituir_toner":
        return f"{base}:{(supply.cor if supply else 'cor_nao_identificada').casefold()}"
    return base


def _title(machine: PrinterMachine, event_type: str) -> str:
    sector = machine.sector or "Local nao informado"
    return f"[Impressora] {EVENT_LABEL[event_type]} - {machine.name} - {sector}"


def _description(
    machine: PrinterMachine,
    *,
    event_type: str,
    original_message: str,
    collection_origin: str,
    detected_at,
    supply: PrinterSupply | None,
) -> str:
    manufacturer = machine.manufacturer or "Nao informado"
    model = machine.model or "Nao informado"
    protheus_code = supply.codigo_protheus if supply else None
    return "\n".join(
        (
            f"Nome: {machine.name}",
            f"Local: {machine.sector or 'Nao informado'}",
            "Ramal: 1010",
            f"Equipamento: {manufacturer} {model}",
            f"Centro de Custo: {machine.cost_center or 'Nao informado'}",
            "Localizacao GLPI: CARIACICA-ES",
            "",
            "Alerta identificado automaticamente pelo Sistema ERP.",
            "",
            f"Tipo de alerta: {EVENT_LABEL[event_type]}",
            f"Mensagem coletada: {original_message}",
            f"Origem da coleta: {collection_origin}",
            f"Data da deteccao: {detected_at.isoformat() if detected_at else 'Nao informada'}",
            "Confirmacao: alerta persistente conforme regra de validacao do ERP",
            "",
            f"Suprimento: {_supply_label(supply, event_type)}",
            f"Codigo Protheus: {protheus_code or 'nao cadastrado'}",
            "",
            "Orientacao:",
            "Solicitar o suprimento no Protheus utilizando o codigo informado acima.",
            "",
            "Chamado aberto automaticamente pelo Sistema ERP.",
        )
    )


def _request_for_alert(
    machine: PrinterMachine,
    alert: AlertaImpressora,
    rule: PrinterAlertRule,
    supply: PrinterSupply | None,
    settings: GlpiSettings,
) -> AbrirChamadoGlpiRequest:
    event_type = EVENT_BY_ALERT_CODE[rule.codigo]
    message = alert.mensagem_original or rule.descricao or EVENT_LABEL[event_type]
    return AbrirChamadoGlpiRequest(
        origem_modulo="impressoras",
        origem_entidade="maquina",
        origem_entidade_id=str(machine.id),
        tipo_evento=event_type,
        titulo=_title(machine, event_type),
        descricao=_description(
            machine,
            event_type=event_type,
            original_message=message,
            collection_origin=alert.origem_coleta,
            detected_at=alert.verificado_em,
            supply=supply,
        ),
        categoria_id=settings.printer_supply_category_id,
        localizacao_id=settings.location_cariacica_id,
        hash_deduplicacao=_deduplication_hash(machine.id, event_type, supply),
        metadados={
            "suprimento_id": supply.id if supply else None,
            "codigo_protheus": supply.codigo_protheus if supply else None,
            "origem_coleta": alert.origem_coleta,
        },
    )


def _resolve_supply(
    db: Session,
    machine: PrinterMachine,
    alert: AlertaImpressora,
    rule: PrinterAlertRule,
) -> PrinterSupply:
    if machine.model_id is None:
        raise SupplyNotFoundError("Modelo da impressora nao cadastrado.")
    if rule.codigo == "replace_drum":
        supply = get_cylinder_supply(db, machine.model_id)
        if supply is None:
            raise SupplyNotFoundError("Cilindro compativel nao cadastrado para o modelo.")
        return supply
    return resolve_toner_supply(
        db,
        model_id=machine.model_id,
        message=alert.mensagem_original or rule.descricao,
    )


def _missing_code_error(machine: PrinterMachine, supply: PrinterSupply) -> str:
    model = f"{machine.manufacturer or ''} {machine.model or ''}".strip()
    return (
        f"Codigo Protheus nao cadastrado para o suprimento "
        f"{_supply_label(supply, 'substituir_toner')} do modelo {model}."
    )


def process_confirmed_printer_supply_alerts(
    db: Session,
    *,
    machine_id: int,
    settings: GlpiSettings | None = None,
    opener=abrir_chamado_glpi,
    blocker=registrar_bloqueio_glpi,
) -> list[ResultadoAberturaGlpi]:
    config = settings or get_glpi_settings()
    if not config.enabled:
        return []
    machine = db.get(PrinterMachine, machine_id)
    if machine is None:
        return []
    alerts = (
        db.query(AlertaImpressora, PrinterAlertRule)
        .join(PrinterAlertRule, PrinterAlertRule.id == AlertaImpressora.regra_alerta_id)
        .filter(
            AlertaImpressora.maquina_id == machine_id,
            PrinterAlertRule.codigo.in_(SUPPORTED_ALERT_CODES),
        )
        .order_by(AlertaImpressora.id.asc())
        .all()
    )
    results: list[ResultadoAberturaGlpi] = []
    for alert, rule in alerts:
        try:
            supply = _resolve_supply(db, machine, alert, rule)
            request = _request_for_alert(machine, alert, rule, supply, config)
            if not supply.codigo_protheus:
                results.append(
                    blocker(
                        db,
                        request,
                        erro=_missing_code_error(machine, supply),
                        settings=config,
                    )
                )
                continue
            results.append(opener(db, request, settings=config))
        except (SupplyNotFoundError, SupplyColorNotIdentifiedError) as exc:
            request = _request_for_alert(machine, alert, rule, None, config)
            results.append(blocker(db, request, erro=str(exc), settings=config))
    return results
