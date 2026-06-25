"""Regras do status atual e da linha do tempo operacional de impressoras."""

import re

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
OFFLINE_ALERT_MESSAGE = "Sem serviço"
SEVERITY_BY_ALERT_LEVEL = {
    "cinza": "unknown",
    "verde": "green",
    "amarelo": "medium",
    "vermelho": "high",
}
COLOR_TRANSLATIONS = {
    "black": "preto",
    "cyan": "ciano",
    "magenta": "magenta",
    "yellow": "amarelo",
}
ALERT_MESSAGE_TRANSLATIONS = (
    (
        re.compile(r"^toner is low(?:\s*\((?P<color>[^)]+)\))?\.?$", re.IGNORECASE),
        "Toner baixo",
    ),
    (
        re.compile(
            r"^drum needs to be replaced soon(?:\s*\((?P<color>[^)]+)\))?\.?$",
            re.IGNORECASE,
        ),
        "Substituir cilindro em breve",
    ),
)


def _classification_from_rule(rule: PrinterAlertRule) -> str:
    return severity_to_visual_classification(
        rule.severidade,
        recognized=rule.codigo not in {"unknown", "sem_retorno_alerta"},
    )


def _message_from_current_alert(alert: AlertaImpressora, rule: PrinterAlertRule) -> str:
    if alert.mensagem_original:
        return _translate_alert_message(str(alert.mensagem_original))
    return rule.descricao or "Sem alerta informado"


def _translate_alert_message(message: str) -> str:
    clean_message = " ".join(message.replace("\x00", "").strip().split())
    for pattern, translated_message in ALERT_MESSAGE_TRANSLATIONS:
        match = pattern.match(clean_message)
        if not match:
            continue
        color = match.groupdict().get("color")
        if not color:
            return translated_message
        translated_color = COLOR_TRANSLATIONS.get(color.strip().casefold(), color.strip())
        return f"{translated_message} ({translated_color})."
    return clean_message


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
                "mensagem": _message_from_current_alert(alert, rule),
            }
            for alert, rule in alerts
        ]
        classified.sort(
            key=lambda item: (
                ALERT_DISPLAY_PRIORITY.get(str(item["classificacao"]), 9),
                str(item["mensagem"]).casefold(),
            )
        )
        overall = calculate_overall_classification(classified)
        primary = classified[0]
        highest_alert_level = str(primary["classificacao"])
        visible_alerts = [
            item
            for item in classified
            if str(item["classificacao"]) == highest_alert_level
        ]
        projections[machine_id] = {
            "nivel_alerta": overall,
            "mensagem_alerta": primary["mensagem"],
            "codigos_alerta": [rule.codigo for _alert, rule in alerts],
            "verificado_em": primary["alert"].verificado_em,
            "alertas": [
                {
                    "codigo": item["rule"].codigo,
                    "mensagem": item["mensagem"],
                    "nivel_alerta": item["classificacao"],
                    "severidade": _severity_from_alert_level(str(item["classificacao"])),
                }
                for item in visible_alerts
            ],
        }
    return projections


def _model_display(manufacturer: str | None, model: str | None) -> str | None:
    if manufacturer and model:
        return f"{manufacturer} - {model}"
    return model or manufacturer


def _severity_from_alert_level(alert_level: str) -> str:
    return SEVERITY_BY_ALERT_LEVEL.get(alert_level, "unknown")


def _display_alert_projection(
    status: StatusImpressora,
    alert_projection: dict[str, object] | None,
) -> dict[str, object]:
    # Offline sempre prevalece sobre alertas antigos ainda persistidos.
    if status.status_operacional != "online":
        return {
            "nivel_alerta": "vermelho",
            "mensagem_alerta": OFFLINE_ALERT_MESSAGE,
            "codigos_alerta": [],
            "alertas": [
                {
                    "codigo": "sem_servico",
                    "mensagem": OFFLINE_ALERT_MESSAGE,
                    "nivel_alerta": "vermelho",
                    "severidade": "high",
                }
            ],
        }

    current_alert = alert_projection or {}
    alert_level = str(current_alert.get("nivel_alerta") or status.nivel_alerta)
    alert_message = str(
        current_alert.get("mensagem_alerta")
        or status.mensagem_alerta
        or "Sem alerta informado"
    )
    return {
        "nivel_alerta": alert_level,
        "mensagem_alerta": alert_message,
        "codigos_alerta": current_alert.get("codigos_alerta") or [],
        "alertas": current_alert.get("alertas")
        or [
            {
                "codigo": "status_atual",
                "mensagem": alert_message,
                "nivel_alerta": alert_level,
                "severidade": _severity_from_alert_level(alert_level),
            }
        ],
    }


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
    manufacturer = machine.manufacturer
    model = machine.model
    model_display = _model_display(manufacturer, model)
    operational_status = "online" if status.status_operacional == "online" else "offline"
    display_alert = _display_alert_projection(status, alert_projection)
    alert_level = str(display_alert["nivel_alerta"])
    alert_message = str(display_alert["mensagem_alerta"])
    return PrinterStatusRead(
        machine_id=machine.id,
        id=machine.id,
        machine_name=machine.name,
        maquina=machine.name,
        ip_address=machine.ip_address,
        ip=machine.ip_address,
        manufacturer=manufacturer,
        fabricante=manufacturer,
        model=model,
        modelo=model,
        modelo_exibicao=model_display,
        url_imagem=machine.printer_model.url_imagem if machine.printer_model else None,
        sector=machine.sector,
        local=machine.sector,
        cost_center=machine.cost_center,
        status_operacional=operational_status,
        status=operational_status,
        nivel_alerta=alert_level,
        severidade=_severity_from_alert_level(alert_level),
        alerta=alert_message,
        alertas=display_alert["alertas"],
        mensagem=alert_message,
        mensagem_alerta=alert_message,
        mensagem_operador=status.mensagem_operador,
        ultima_verificacao_em=status.ultima_verificacao_em,
        verificado_em=status.ultima_verificacao_em,
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
                _display_alert_projection(
                    status,
                    alert_projections.get(status.maquina_id),
                )["nivel_alerta"]
            )
            in {"amarelo", "vermelho"}
            for status in statuses
        ),
        # Regra transitória até existir um domínio próprio para suprimentos.
        substituir_toner=sum(
            status.status_operacional == "online"
            and (
                "replace_toner"
                in (
                    _display_alert_projection(
                        status,
                        alert_projections.get(status.maquina_id),
                    ).get("codigos_alerta")
                    or []
                )
                or "substituir toner"
                in str(
                    _display_alert_projection(
                        status,
                        alert_projections.get(status.maquina_id),
                    )["mensagem_alerta"]
                ).casefold()
            )
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
