"""Regras do status atual e da linha do tempo operacional de impressoras."""

from sqlalchemy.orm import Session, joinedload

from backend.app.modules.printers.machines.models import PrinterMachine
from backend.app.modules.printers.monitoring.alerts.models import AlertaImpressora
from backend.app.modules.printers.monitoring.snmp.alert_collector import (
    calculate_overall_classification,
    severity_to_visual_classification,
)
from backend.app.modules.printers.monitoring.state.models import PrinterAlertRule
from backend.app.modules.printers.status.models import LogImpressora, StatusImpressora
from backend.app.modules.printers.status.schemas import (
    PrinterLogRead,
    PrinterStatusRead,
    PrinterStatusSummary,
)


class PrinterStatusNotFoundError(Exception):
    pass


ALERT_DISPLAY_PRIORITY = {
    "vermelho": 0,
    "amarelo": 1,
    "cinza": 2,
    "verde": 3,
}


def _classification_from_rule(rule: PrinterAlertRule) -> str:
    return severity_to_visual_classification(
        rule.severidade,
        recognized=rule.codigo not in {"unknown", "sem_retorno_alerta"},
    )


def _message_from_current_alert(alert: AlertaImpressora, rule: PrinterAlertRule) -> str:
    if alert.mensagem_original:
        return str(alert.mensagem_original)
    return rule.descricao or "Sem alerta informado"


def _alert_projection_for_rows(
    db: Session,
    machine_ids: list[int],
) -> dict[int, dict[str, object]]:
    if not machine_ids:
        return {}

    rows = (
        db.query(AlertaImpressora, PrinterAlertRule)
        .join(PrinterAlertRule, PrinterAlertRule.id == AlertaImpressora.regra_alerta_id)
        .filter(AlertaImpressora.maquina_id.in_(machine_ids))
        .all()
    )
    grouped: dict[int, list[tuple[AlertaImpressora, PrinterAlertRule]]] = {}
    for alert, rule in rows:
        grouped.setdefault(alert.maquina_id, []).append((alert, rule))

    projections: dict[int, dict[str, object]] = {}
    for machine_id, alerts in grouped.items():
        classified = [
            {
                "alert": alert,
                "rule": rule,
                "classificacao": _classification_from_rule(rule),
            }
            for alert, rule in alerts
        ]
        overall = calculate_overall_classification(classified)
        primary = min(
            classified,
            key=lambda item: ALERT_DISPLAY_PRIORITY.get(str(item["classificacao"]), 9),
        )
        projections[machine_id] = {
            "nivel_alerta": overall,
            "mensagem_alerta": _message_from_current_alert(
                primary["alert"],
                primary["rule"],
            ),
            "codigos_alerta": [rule.codigo for _alert, rule in alerts],
            "verificado_em": primary["alert"].verificado_em,
        }
    return projections


# ---------------------------------------------------------------------
# 📌 STATUS INICIAL DA MÁQUINA
# ---------------------------------------------------------------------
# Toda máquina nasce com uma fotografia operacional neutra. Isso permite que a
# consulta permaneça consistente antes de existir monitoramento automático.
def create_initial_status(db: Session, machine_id: int, *, origem: str = "sistema") -> StatusImpressora:
    current = db.query(StatusImpressora).filter(StatusImpressora.maquina_id == machine_id).one_or_none()
    if current is not None:
        return current

    status = StatusImpressora(
        maquina_id=machine_id,
        status_operacional="desconhecido",
        nivel_alerta="cinza",
        mensagem_alerta="Ainda nao verificada",
        mensagem_operador="Aguardando primeira verificacao.",
        origem=origem,
    )
    db.add(status)
    db.flush()
    return status


def _status_to_read(
    status: StatusImpressora,
    *,
    alert_projection: dict[str, object] | None = None,
) -> PrinterStatusRead:
    machine = status.maquina
    current_alert = alert_projection or {}
    alert_checked_at = current_alert.get("verificado_em")
    return PrinterStatusRead(
        machine_id=machine.id,
        machine_name=machine.name,
        ip_address=machine.ip_address,
        manufacturer=machine.manufacturer,
        model=machine.model,
        url_imagem=machine.printer_model.url_imagem if machine.printer_model else None,
        sector=machine.sector,
        cost_center=machine.cost_center,
        status_operacional="online" if status.status_operacional == "online" else "offline",
        nivel_alerta=str(current_alert.get("nivel_alerta") or status.nivel_alerta),
        mensagem_alerta=str(
            current_alert.get("mensagem_alerta")
            or status.mensagem_alerta
            or "Sem alerta informado"
        ),
        mensagem_operador=status.mensagem_operador,
        ultima_verificacao_em=alert_checked_at or status.ultima_verificacao_em,
        ultimo_sucesso_em=status.ultimo_sucesso_em,
        ultima_falha_em=status.ultima_falha_em,
        tempo_resposta_ms=status.tempo_resposta_ms,
        metodo_confirmacao=status.metodo_confirmacao,
        origem=status.origem,
        resposta_bruta=status.resposta_bruta,
    )


# ---------------------------------------------------------------------
# 📌 CENTRAL OPERACIONAL SOMENTE PARA MÁQUINAS ATIVAS
# ---------------------------------------------------------------------
# A inativação preserva cadastro e histórico, mas remove a máquina das listas
# e dos totais operacionais. Máquinas inativas continuam visíveis em Máquinas.
def list_printer_statuses(db: Session) -> list[PrinterStatusRead]:
    statuses = (
        db.query(StatusImpressora)
        .join(StatusImpressora.maquina)
        .options(
            joinedload(StatusImpressora.maquina).joinedload(PrinterMachine.printer_model),
        )
        .filter(PrinterMachine.is_active.is_(True))
        .order_by(PrinterMachine.name.asc(), PrinterMachine.id.asc())
        .all()
    )
    alert_projections = _alert_projection_for_rows(
        db,
        [status.maquina_id for status in statuses],
    )
    return [
        _status_to_read(
            status,
            alert_projection=alert_projections.get(status.maquina_id),
        )
        for status in statuses
    ]


def summarize_printer_statuses(db: Session) -> PrinterStatusSummary:
    statuses = (
        db.query(StatusImpressora)
        .join(StatusImpressora.maquina)
        .filter(PrinterMachine.is_active.is_(True))
        .all()
    )
    alert_projections = _alert_projection_for_rows(
        db,
        [status.maquina_id for status in statuses],
    )
    return PrinterStatusSummary(
        total_impressoras=len(statuses),
        online=sum(status.status_operacional == "online" for status in statuses),
        offline=sum(status.status_operacional != "online" for status in statuses),
        com_alerta=sum(
            str(
                alert_projections.get(status.maquina_id, {}).get("nivel_alerta")
                or status.nivel_alerta
            )
            in {"amarelo", "vermelho"}
            for status in statuses
        ),
        # Regra transitória até existir um domínio próprio para suprimentos.
        substituir_toner=sum(
            "replace_toner"
            in (alert_projections.get(status.maquina_id, {}).get("codigos_alerta") or [])
            or "substituir toner"
            in str(
                alert_projections.get(status.maquina_id, {}).get("mensagem_alerta")
                or status.mensagem_alerta
                or ""
            ).casefold()
            for status in statuses
        ),
    )


def get_printer_status(db: Session, machine_id: int) -> StatusImpressora:
    status = (
        db.query(StatusImpressora)
        .options(
            joinedload(StatusImpressora.maquina).joinedload(PrinterMachine.printer_model),
        )
        .filter(StatusImpressora.maquina_id == machine_id)
        .one_or_none()
    )
    if status is None:
        raise PrinterStatusNotFoundError
    return status


def read_printer_status(db: Session, machine_id: int) -> PrinterStatusRead:
    status = get_printer_status(db, machine_id)
    return _status_to_read(
        status,
        alert_projection=_alert_projection_for_rows(db, [machine_id]).get(machine_id),
    )


def list_printer_logs(db: Session, machine_id: int, *, limit: int = 50) -> list[PrinterLogRead]:
    get_printer_status(db, machine_id)
    logs = (
        db.query(LogImpressora)
        .filter(LogImpressora.maquina_id == machine_id)
        .order_by(LogImpressora.criado_em.desc(), LogImpressora.id.desc())
        .limit(limit)
        .all()
    )
    return [
        PrinterLogRead(
            id=log.id,
            machine_id=log.maquina_id,
            tipo_evento=log.tipo_evento,
            status_anterior=log.status_anterior,
            status_novo=log.status_novo,
            alerta_anterior=log.alerta_anterior,
            alerta_novo=log.alerta_novo,
            mensagem=log.mensagem,
            verificado_em=log.verificado_em,
            tempo_resposta_ms=log.tempo_resposta_ms,
            origem=log.origem,
            resposta_bruta=log.resposta_bruta,
            criado_em=log.criado_em,
        )
        for log in logs
    ]
