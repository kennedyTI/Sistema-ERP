"""Regras do status atual e da linha do tempo operacional de impressoras."""

import re
from datetime import timedelta

from sqlalchemy.orm import Session, joinedload

from backend.app.modules.printers.machines.models import PrinterMachine
from backend.app.core.timezone import now_sao_paulo
from backend.app.modules.printers.monitoring.alerts.models import (
    AlertaImpressora,
    HistoricoAlertaImpressora,
)
from backend.app.modules.printers.monitoring.snmp.alert_collector import (
    severity_to_visual_classification,
)
from backend.app.modules.printers.monitoring.state.models import PrinterAlertRule
from backend.app.modules.printers.monitoring.toner.models import StatusTonerImpressora
from backend.app.modules.printers.monitoring.toner.alert_policy import (
    reconcile_toner_alerts,
)
from backend.app.modules.printers.monitoring.toner.services import list_toners_for_machines
from backend.app.modules.printers.status.models import (
    HistoricoStatusImpressora,
    StatusImpressora,
)
from backend.app.modules.printers.status.schemas import (
    PrinterLogRead,
    PrinterStatusRead,
    PrinterStatusSummary,
)
from backend.app.modules.printers.supplies.models import PrinterSupply
from backend.app.modules.printers.supplies.services import list_supplies_for_models


class PrinterStatusNotFoundError(Exception):
    pass


SEVERITY_WEIGHT = {
    "high": 50,
    "medium": 40,
    "low": 30,
    "unknown": 20,
    "green": 10,
}
OFFLINE_ALERT_MESSAGE = "Sem serviço"
NO_ALERT_MESSAGE = "Sem alerta"
RECENT_LOG_WINDOW_HOURS = 24
MAX_RECENT_LOGS = 10
HEX_ALERT_PATTERN = re.compile(r"^0x[0-9a-f]+$", re.IGNORECASE)
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
TONER_NAMES = {
    "black": "Preto",
    "cyan": "Ciano",
    "magenta": "Magenta",
    "yellow": "Amarelo",
    "unknown": "Desconhecido",
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
    (
        re.compile(r"^paper is out(?:\s*\((?P<detail>[^)]+)\))?\.?$", re.IGNORECASE),
        "Sem papel",
    ),
)


def _classification_from_rule(rule: PrinterAlertRule) -> str:
    return severity_to_visual_classification(
        _safe_severity(rule.severidade),
        recognized=rule.codigo not in {"unknown", "sem_retorno_alerta"},
    )


def _safe_severity(value: str | None) -> str:
    return value if value in SEVERITY_WEIGHT else "unknown"


def severity_weight(value: str | None) -> int:
    return SEVERITY_WEIGHT[_safe_severity(value)]


def _alert_sort_key(item: dict[str, object]) -> tuple[int, int, str, str]:
    rule = item["rule"]
    assert isinstance(rule, PrinterAlertRule)
    # Na Rules Engine, o menor numero representa a regra mais importante.
    return (
        -severity_weight(str(item["severidade"])),
        rule.prioridade,
        str(item["mensagem"]).casefold(),
        rule.codigo.casefold(),
    )


def _projected_alert_sort_key(item: dict[str, object]) -> tuple[int, int, str, str]:
    return (
        -severity_weight(str(item.get("severidade"))),
        int(item.get("prioridade") or 1000),
        str(item.get("mensagem") or "").casefold(),
        str(item.get("codigo") or "").casefold(),
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
        detail = match.groupdict().get("color") or match.groupdict().get("detail")
        if not detail:
            return translated_message
        translated_detail = _translate_alert_detail(detail)
        return f"{translated_message} ({translated_detail})."
    return clean_message


def _translate_alert_detail(detail: str) -> str:
    clean_detail = detail.strip()
    translated_color = COLOR_TRANSLATIONS.get(clean_detail.casefold())
    if translated_color:
        return translated_color
    if re.fullmatch(r"[a-z]+\d+", clean_detail, re.IGNORECASE):
        return clean_detail.upper()
    return clean_detail


def _is_neutral_technical_alert(item: dict[str, object]) -> bool:
    rule = item["rule"]
    message = str(item["mensagem"] or "").strip()
    if isinstance(rule, PrinterAlertRule) and rule.codigo == "sem_retorno_alerta":
        return True
    return (
        isinstance(rule, PrinterAlertRule)
        and rule.codigo == "unknown"
        and str(item["classificacao"]) == "cinza"
        and (not message or HEX_ALERT_PATTERN.match(message) is not None)
    )


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
                "severidade": _safe_severity(rule.severidade),
            }
            for alert, rule in alerts
        ]
        classified = [
            item for item in classified if not _is_neutral_technical_alert(item)
        ]
        if not classified:
            continue
        classified.sort(key=_alert_sort_key)
        primary = classified[0]
        projections[machine_id] = {
            "nivel_alerta": primary["classificacao"],
            "severidade": primary["severidade"],
            "mensagem_alerta": primary["mensagem"],
            "codigos_alerta": [item["rule"].codigo for item in classified],
            "verificado_em": primary["alert"].verificado_em,
            "alertas": [
                {
                    "codigo": item["rule"].codigo,
                    "mensagem": item["mensagem"],
                    "nivel_alerta": item["classificacao"],
                    "severidade": item["severidade"],
                    "prioridade": item["rule"].prioridade,
                }
                for item in classified
            ],
        }
    return projections


def _model_display(manufacturer: str | None, model: str | None) -> str | None:
    if manufacturer and model:
        return f"{manufacturer} - {model}"
    return model or manufacturer


def _toner_aware_alert_projection(
    alert_projection: dict[str, object] | None,
    toner_rows: list[StatusTonerImpressora] | None,
    *,
    printer_model,
) -> dict[str, object] | None:
    current_alerts = list((alert_projection or {}).get("alertas") or [])
    reconciled = reconcile_toner_alerts(
        current_alerts,
        toner_rows,
        printer_model=printer_model,
    )
    if not reconciled:
        return None
    reconciled.sort(key=_projected_alert_sort_key)
    primary = reconciled[0]
    return {
        "nivel_alerta": primary["nivel_alerta"],
        "severidade": primary["severidade"],
        "mensagem_alerta": primary["mensagem"],
        "codigos_alerta": [alert["codigo"] for alert in reconciled],
        "verificado_em": (alert_projection or {}).get("verificado_em"),
        "alertas": reconciled,
    }


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
            "severidade": "high",
            "mensagem_alerta": OFFLINE_ALERT_MESSAGE,
            "codigos_alerta": [],
            "alertas": [
                {
                    "codigo": "sem_servico",
                    "mensagem": OFFLINE_ALERT_MESSAGE,
                    "nivel_alerta": "vermelho",
                    "severidade": "high",
                    "prioridade": 6,
                }
            ],
        }

    if not alert_projection:
        return {
            "nivel_alerta": "cinza",
            "severidade": "unknown",
            "mensagem_alerta": NO_ALERT_MESSAGE,
            "codigos_alerta": [],
            "alertas": [],
        }

    current_alert = alert_projection
    alert_level = str(current_alert.get("nivel_alerta") or status.nivel_alerta)
    alert_message = str(
        current_alert.get("mensagem_alerta")
        or status.mensagem_alerta
        or "Sem alerta informado"
    )
    return {
        "nivel_alerta": alert_level,
        "severidade": current_alert.get("severidade")
        or _severity_from_alert_level(alert_level),
        "mensagem_alerta": alert_message,
        "codigos_alerta": current_alert.get("codigos_alerta") or [],
        "alertas": current_alert.get("alertas")
        or [
            {
                "codigo": "status_atual",
                "mensagem": alert_message,
                "nivel_alerta": alert_level,
                "severidade": _severity_from_alert_level(alert_level),
                "prioridade": 1000,
            }
        ],
    }


SUPPLY_COLOR_BY_TONER_COLOR = {
    "black": "PRETO",
    "cyan": "CIANO",
    "magenta": "MAGENTA",
    "yellow": "AMARELO",
}


def _toners_to_read(
    rows: list[StatusTonerImpressora] | None,
    supplies: list[PrinterSupply] | None,
) -> list[dict[str, object]]:
    code_by_color = {
        supply.cor: supply.codigo_protheus
        for supply in (supplies or [])
        if supply.suprimento == "TONER"
    }
    return [
        {
            "cor": row.cor,
            "nome": TONER_NAMES.get(row.cor, "Desconhecido"),
            "percentual": row.percentual,
            "descricao": row.descricao_coletada,
            "origem_coleta": row.origem_coleta,
            "metodo_coleta": row.metodo_coleta,
            "coletado_em": row.coletado_em,
            "codigo_protheus": code_by_color.get(
                SUPPLY_COLOR_BY_TONER_COLOR.get(row.cor)
            ),
        }
        for row in (rows or [])
    ]


def _supplies_to_read(
    supplies: list[PrinterSupply] | None,
    *,
    supply_type: str,
) -> list[dict[str, object]]:
    return [
        {
            "id": supply.id,
            "suprimento": supply.suprimento,
            "cor": supply.cor,
            "codigo_protheus": supply.codigo_protheus,
        }
        for supply in (supplies or [])
        if supply.suprimento == supply_type
    ]


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
    toner_rows: list[StatusTonerImpressora] | None = None,
    supply_rows: list[PrinterSupply] | None = None,
) -> PrinterStatusRead:
    machine = status.maquina
    manufacturer = machine.manufacturer
    model = machine.model
    model_display = _model_display(manufacturer, model)
    operational_status = "online" if status.status_operacional == "online" else "offline"
    toner_aware_projection = _toner_aware_alert_projection(
        alert_projection,
        toner_rows,
        printer_model=machine.printer_model,
    )
    display_alert = _display_alert_projection(status, toner_aware_projection)
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
        severidade=str(display_alert["severidade"]),
        alerta=alert_message,
        alertas=display_alert["alertas"],
        toners=_toners_to_read(toner_rows, supply_rows),
        suprimentos_toner=_supplies_to_read(supply_rows, supply_type="TONER"),
        cilindro=next(
            iter(_supplies_to_read(supply_rows, supply_type="CILINDRO")),
            None,
        ),
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
    toner_projections = list_toners_for_machines(
        db,
        [status.maquina_id for status in statuses],
    )
    supply_projections = list_supplies_for_models(
        db,
        [
            status.maquina.model_id
            for status in statuses
            if status.maquina.model_id is not None
        ],
    )
    return [
        _status_to_read(
            status,
            alert_projection=alert_projections.get(status.maquina_id),
            toner_rows=toner_projections.get(status.maquina_id),
            supply_rows=supply_projections.get(status.maquina.model_id),
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
    toner_projections = list_toners_for_machines(
        db,
        [status.maquina_id for status in statuses],
    )
    display_alerts = {
        status.maquina_id: _display_alert_projection(
            status,
            _toner_aware_alert_projection(
                alert_projections.get(status.maquina_id),
                toner_projections.get(status.maquina_id),
                printer_model=status.maquina.printer_model,
            ),
        )
        for status in statuses
    }
    return PrinterStatusSummary(
        total_impressoras=len(statuses),
        online=sum(status.status_operacional == "online" for status in statuses),
        offline=sum(status.status_operacional != "online" for status in statuses),
        com_alerta=sum(
            str(display_alerts[status.maquina_id]["nivel_alerta"])
            in {"amarelo", "vermelho"}
            for status in statuses
        ),
        # 📌 O card considera alertas textuais ou calculados pelo percentual.
        substituir_toner=sum(
            status.status_operacional == "online"
            and (
                any(
                    code
                    in {
                        "replace_toner",
                        "toner_low",
                        "toner_percentual_baixo",
                        "toner_percentual_critico",
                    }
                    for code in (
                        display_alerts[status.maquina_id].get("codigos_alerta") or []
                    )
                )
                or "substituir toner"
                in str(display_alerts[status.maquina_id]["mensagem_alerta"]).casefold()
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
    supplies = (
        list_supplies_for_models(db, [status.maquina.model_id]).get(status.maquina.model_id)
        if status.maquina.model_id is not None
        else []
    )
    return _status_to_read(
        status,
        alert_projection=_alert_projection_for_rows(db, [machine_id]).get(machine_id),
        toner_rows=list_toners_for_machines(db, [machine_id]).get(machine_id),
        supply_rows=supplies,
    )


def _status_history_message(history: HistoricoStatusImpressora) -> str:
    if history.status_novo == "online":
        if history.status_anterior == "offline":
            return "Impressora voltou a ficar Online"
        return "Primeira confirmacao: impressora Online"
    if history.status_anterior == "online":
        return "Impressora ficou Offline"
    return "Primeira confirmacao: impressora Offline"


def _alert_history_message(
    history: HistoricoAlertaImpressora,
    rule: PrinterAlertRule,
) -> str:
    if history.codigo_evento == "alerta_nao_catalogado":
        return "Alerta nao catalogado detectado"

    description = rule.descricao or "Alerta operacional"
    if history.codigo_evento == "estado_inicial_alerta":
        return f"Alerta detectado: {description}"
    return f"Alerta alterado: {description}"


def _history_matches_new_classification(
    history: HistoricoAlertaImpressora,
    rule: PrinterAlertRule,
) -> bool:
    if history.codigo_evento != "classificacao_alterada":
        return True
    history_classification = severity_to_visual_classification(
        _safe_severity(history.severidade),
        recognized=rule.codigo not in {"unknown", "sem_retorno_alerta"},
    )
    return history_classification == history.classificacao_nova


def list_printer_logs(db: Session, machine_id: int, *, limit: int = 10) -> list[PrinterLogRead]:
    """Une os historicos operacionais recentes sem expor detalhes tecnicos."""
    get_printer_status(db, machine_id)
    effective_limit = min(max(limit, 1), MAX_RECENT_LOGS)
    cutoff = now_sao_paulo() - timedelta(hours=RECENT_LOG_WINDOW_HOURS)

    status_history = (
        db.query(HistoricoStatusImpressora)
        .filter(
            HistoricoStatusImpressora.maquina_id == machine_id,
            HistoricoStatusImpressora.verificado_em >= cutoff,
        )
        .order_by(
            HistoricoStatusImpressora.verificado_em.desc(),
            HistoricoStatusImpressora.id.desc(),
        )
        .limit(effective_limit)
        .all()
    )

    alert_history = (
        db.query(HistoricoAlertaImpressora, PrinterAlertRule)
        .join(
            PrinterAlertRule,
            PrinterAlertRule.id == HistoricoAlertaImpressora.regra_alerta_id,
        )
        .filter(
            HistoricoAlertaImpressora.maquina_id == machine_id,
            HistoricoAlertaImpressora.verificado_em >= cutoff,
        )
        .order_by(
            HistoricoAlertaImpressora.verificado_em.desc(),
            HistoricoAlertaImpressora.id.desc(),
        )
        .limit(effective_limit)
        .all()
    )

    events = [
        PrinterLogRead(
            id=f"status:{history.id}",
            data_hora=history.verificado_em,
            tipo=history.codigo_evento,
            mensagem=_status_history_message(history),
            origem="status",
        )
        for history in status_history
    ]
    events.extend(
        PrinterLogRead(
            id=f"alerta:{history.id}",
            data_hora=history.verificado_em,
            tipo=history.codigo_evento,
            mensagem=_alert_history_message(history, rule),
            origem="alerta",
        )
        for history, rule in alert_history
        if _history_matches_new_classification(history, rule)
    )
    events.sort(key=lambda event: (event.data_hora, event.id), reverse=True)
    return events[:effective_limit]
