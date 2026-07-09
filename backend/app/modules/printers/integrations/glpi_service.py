"""Monta chamados de suprimentos sem conhecer detalhes HTTP do GLPI."""

from __future__ import annotations

from dataclasses import dataclass

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
from backend.app.modules.printers.monitoring.toner.models import StatusTonerImpressora
from backend.app.modules.printers.supplies.models import PrinterSupply
from backend.app.modules.printers.supplies.services import (
    get_cylinder_supply,
    get_toner_supplies,
)


TONER_CRITICAL_THRESHOLD = 10
TONER_EVENT_TYPE = "toner_abaixo_10"
DRUM_EVENT_TYPE = "substituir_cilindro"
TONER_COLOR_BY_STATUS_COLOR = {
    "black": "PRETO",
    "cyan": "CIANO",
    "magenta": "MAGENTA",
    "yellow": "AMARELO",
}
TONER_COLOR_NAMES = {
    "PRETO": "preto",
    "CIANO": "ciano",
    "MAGENTA": "magenta",
    "AMARELO": "amarelo",
}
TONER_COLOR_ORDER = ("PRETO", "CIANO", "MAGENTA", "AMARELO")


@dataclass(frozen=True)
class SupplyItem:
    supply: PrinterSupply | None
    color: str | None
    percent: int | None = None


def _supply_label(supply: PrinterSupply | None, event_type: str) -> str:
    if supply is None:
        return "TONER" if event_type == TONER_EVENT_TYPE else "CILINDRO"
    return " ".join(value for value in (supply.suprimento, supply.cor) if value)


def _toner_deduplication_hash(machine_id: int) -> str:
    return f"impressoras:maquina:{machine_id}:toner_abaixo_10"


def _drum_deduplication_hash(machine_id: int) -> str:
    return f"impressoras:maquina:{machine_id}:substituir_cilindro"


def _location(machine: PrinterMachine) -> str:
    return machine.sector or "Nao informado"


def _machine_model(machine: PrinterMachine) -> str:
    manufacturer = machine.manufacturer or "Nao informado"
    model = machine.model or "Nao informado"
    return f"{manufacturer} {model}".strip()


def _join_readable(items: list[str]) -> str:
    if len(items) <= 1:
        return items[0] if items else ""
    if len(items) == 2:
        return " e ".join(items)
    return ", ".join(items[:-1]) + f" e {items[-1]}"


def _product_codes(items: list[SupplyItem]) -> str:
    parts: list[str] = []
    for item in items:
        if item.supply is None:
            label = item.color or "SUPRIMENTO"
            code = "nao cadastrado"
        elif item.supply.suprimento == "CILINDRO":
            label = "CILINDRO"
            code = item.supply.codigo_protheus or "nao cadastrado"
        else:
            label = item.supply.cor or item.color or "TONER"
            code = item.supply.codigo_protheus or "nao cadastrado"
        parts.append(f"{label} {code}")
    return " | ".join(parts)


def _base_body(machine: PrinterMachine, product_codes: str) -> list[str]:
    return [
        f"Local: {_location(machine)}",
        f"Nome da máquina: {machine.name or 'Nao informado'}",
        f"Modelo: {_machine_model(machine)}",
        f"IP: {machine.ip_address or 'Nao informado'}",
        f"Centro de custo: {machine.cost_center or 'Nao informado'}",
        f"Código do produto: {product_codes}",
        "",
    ]


def _toner_description(machine: PrinterMachine, items: list[SupplyItem]) -> str:
    colors = [
        TONER_COLOR_NAMES.get(item.color or "", (item.color or "").casefold())
        for item in items
    ]
    body = _base_body(machine, _product_codes(items))
    body.append(
        f"O(s) toner(s) {_join_readable(colors)} da impressora {machine.name} "
        "está(ão) em nível crítico, até 10%. Chamado aberto para acompanhamento técnico!"
    )
    return "\n".join(body)


def _drum_description(machine: PrinterMachine, supply: PrinterSupply | None) -> str:
    body = _base_body(machine, _product_codes([SupplyItem(supply=supply, color=None)]))
    body.append(
        f"O cilindro da impressora {machine.name} precisa ser substituído. "
        "Chamado aberto para acompanhamento técnico!"
    )
    return "\n".join(body)


def _missing_machine_data(machine: PrinterMachine) -> list[str]:
    missing = []
    if not machine.sector:
        missing.append("local")
    if not machine.name:
        missing.append("nome da maquina")
    if not machine.manufacturer or not machine.model:
        missing.append("fabricante/modelo")
    if not machine.ip_address:
        missing.append("IP")
    if not machine.cost_center:
        missing.append("centro de custo")
    return missing


def _base_request(
    machine: PrinterMachine,
    *,
    event_type: str,
    title: str,
    description: str,
    deduplication_hash: str,
    metadata: dict[str, object],
    settings: GlpiSettings,
) -> AbrirChamadoGlpiRequest:
    return AbrirChamadoGlpiRequest(
        origem_modulo="impressoras",
        origem_entidade="maquina",
        origem_entidade_id=str(machine.id),
        tipo_evento=event_type,
        titulo=title,
        descricao=description,
        categoria_id=settings.printer_supply_category_id,
        localizacao_id=settings.location_cariacica_id,
        urgency=settings.default_urgency,
        requester_user_id=settings.requester_user_id,
        assign_user_id=settings.assign_user_id,
        assign_group_id=settings.assign_group_id,
        hash_deduplicacao=deduplication_hash,
        metadados=metadata,
    )


def _missing_code_error(
    machine: PrinterMachine,
    supply: PrinterSupply,
    *,
    event_type: str,
) -> str:
    model = f"{machine.manufacturer or ''} {machine.model or ''}".strip()
    return (
        f"Codigo Protheus nao cadastrado para o suprimento "
        f"{_supply_label(supply, event_type)} do modelo {model}."
    )


def _toner_sort_key(row: StatusTonerImpressora) -> tuple[int, str, str]:
    color = TONER_COLOR_BY_STATUS_COLOR.get(row.cor)
    order = TONER_COLOR_ORDER.index(color) if color in TONER_COLOR_ORDER else 99
    return order, row.cor, row.indice_suprimento


def _request_for_toner(
    db: Session,
    machine: PrinterMachine,
    critical_toners: list[StatusTonerImpressora],
    settings: GlpiSettings,
) -> tuple[AbrirChamadoGlpiRequest, str | None]:
    items: list[SupplyItem] = []
    error: str | None = None
    supplies_by_color: dict[str, PrinterSupply] = {}
    if machine.model_id is not None:
        supplies_by_color = {
            supply.cor: supply
            for supply in get_toner_supplies(db, machine.model_id)
            if supply.cor is not None
        }
    else:
        error = "Modelo da impressora nao cadastrado."

    seen_colors: set[str] = set()
    sorted_toners = sorted(critical_toners, key=_toner_sort_key)
    for toner in sorted_toners:
        color = TONER_COLOR_BY_STATUS_COLOR.get(toner.cor)
        if color is None:
            error = (
                "Cor do toner critico nao identificada com seguranca para abertura "
                "de chamado."
            )
            items.append(
                SupplyItem(
                    supply=None,
                    color=(toner.cor or "DESCONHECIDO").upper(),
                    percent=toner.percentual,
                )
            )
            continue
        if color in seen_colors:
            continue
        seen_colors.add(color)
        supply = supplies_by_color.get(color)
        items.append(SupplyItem(supply=supply, color=color, percent=toner.percentual))
        if supply is None:
            error = f"Toner {color} nao cadastrado para o modelo."
        elif not supply.codigo_protheus:
            error = _missing_code_error(machine, supply, event_type=TONER_EVENT_TYPE)

    missing = _missing_machine_data(machine)
    if missing:
        error = (
            "Dados obrigatorios ausentes para abertura do chamado: "
            + ", ".join(missing)
            + "."
        )

    request = _base_request(
        machine,
        event_type=TONER_EVENT_TYPE,
        title=f"Toner crítico até 10% - {_location(machine)}",
        description=_toner_description(machine, items),
        deduplication_hash=_toner_deduplication_hash(machine.id),
        metadata={
            "evento": TONER_EVENT_TYPE,
            "limite_percentual": TONER_CRITICAL_THRESHOLD,
            "cores": [item.color for item in items],
            "codigos_protheus": [
                item.supply.codigo_protheus if item.supply else None for item in items
            ],
            "percentuais": [item.percent for item in items],
        },
        settings=settings,
    )
    return request, error


def _request_for_drum(
    db: Session,
    machine: PrinterMachine,
    alert: AlertaImpressora,
    settings: GlpiSettings,
) -> tuple[AbrirChamadoGlpiRequest, str | None]:
    supply: PrinterSupply | None = None
    error: str | None = None
    if machine.model_id is None:
        error = "Modelo da impressora nao cadastrado."
    else:
        supply = get_cylinder_supply(db, machine.model_id)
        if supply is None:
            error = "Cilindro compativel nao cadastrado para o modelo."
        elif not supply.codigo_protheus:
            error = _missing_code_error(machine, supply, event_type=DRUM_EVENT_TYPE)

    missing = _missing_machine_data(machine)
    if missing:
        error = (
            "Dados obrigatorios ausentes para abertura do chamado: "
            + ", ".join(missing)
            + "."
        )

    request = _base_request(
        machine,
        event_type=DRUM_EVENT_TYPE,
        title=f"Substituir cilindro - {_location(machine)}",
        description=_drum_description(machine, supply),
        deduplication_hash=_drum_deduplication_hash(machine.id),
        metadata={
            "evento": DRUM_EVENT_TYPE,
            "suprimento_id": supply.id if supply else None,
            "codigo_protheus": supply.codigo_protheus if supply else None,
            "origem_coleta": alert.origem_coleta,
            "mensagem_original": alert.mensagem_original,
        },
        settings=settings,
    )
    return request, error


def _critical_toner_rows(db: Session, machine_id: int) -> list[StatusTonerImpressora]:
    return (
        db.query(StatusTonerImpressora)
        .filter(
            StatusTonerImpressora.maquina_id == machine_id,
            StatusTonerImpressora.percentual.is_not(None),
            StatusTonerImpressora.percentual <= TONER_CRITICAL_THRESHOLD,
        )
        .order_by(StatusTonerImpressora.cor.asc(), StatusTonerImpressora.id.asc())
        .all()
    )


def _drum_alerts(db: Session, machine_id: int) -> list[AlertaImpressora]:
    return [
        alert
        for alert, _rule in (
            db.query(AlertaImpressora, PrinterAlertRule)
            .join(PrinterAlertRule, PrinterAlertRule.id == AlertaImpressora.regra_alerta_id)
            .filter(
                AlertaImpressora.maquina_id == machine_id,
                PrinterAlertRule.codigo == "replace_drum",
            )
            .order_by(AlertaImpressora.id.asc())
            .all()
        )
    ]


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

    results: list[ResultadoAberturaGlpi] = []
    critical_toners = _critical_toner_rows(db, machine_id)
    if critical_toners:
        request, error = _request_for_toner(db, machine, critical_toners, config)
        if error:
            results.append(blocker(db, request, erro=error, settings=config))
        else:
            results.append(opener(db, request, settings=config))

    drum_alerts = _drum_alerts(db, machine_id)
    if drum_alerts:
        request, error = _request_for_drum(db, machine, drum_alerts[0], config)
        if error:
            results.append(blocker(db, request, erro=error, settings=config))
        else:
            results.append(opener(db, request, settings=config))
    return results
