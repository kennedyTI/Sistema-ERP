"""Regras do status atual e da linha do tempo operacional de impressoras."""

from sqlalchemy.orm import Session, joinedload

from backend.app.modules.printers.machines.models import PrinterMachine
from backend.app.modules.printers.status.models import LogImpressora, StatusImpressora
from backend.app.modules.printers.status.schemas import (
    PrinterLogRead,
    PrinterStatusRead,
    PrinterStatusSummary,
)


class PrinterStatusNotFoundError(Exception):
    pass


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


def _status_to_read(status: StatusImpressora) -> PrinterStatusRead:
    machine = status.maquina
    return PrinterStatusRead(
        machine_id=machine.id,
        machine_name=machine.name,
        ip_address=machine.ip_address,
        manufacturer=machine.manufacturer,
        model=machine.model,
        url_imagem=machine.printer_model.url_imagem if machine.printer_model else None,
        sector=machine.sector,
        cost_center=machine.cost_center,
        status_operacional=status.status_operacional,
        nivel_alerta=status.nivel_alerta,
        mensagem_alerta=status.mensagem_alerta,
        mensagem_operador=status.mensagem_operador,
        ultima_verificacao_em=status.ultima_verificacao_em,
        ultimo_sucesso_em=status.ultimo_sucesso_em,
        ultima_falha_em=status.ultima_falha_em,
        tempo_resposta_ms=status.tempo_resposta_ms,
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
    return [_status_to_read(status) for status in statuses]


def summarize_printer_statuses(db: Session) -> PrinterStatusSummary:
    statuses = (
        db.query(StatusImpressora)
        .join(StatusImpressora.maquina)
        .filter(PrinterMachine.is_active.is_(True))
        .all()
    )
    return PrinterStatusSummary(
        total_impressoras=len(statuses),
        online=sum(status.status_operacional == "online" for status in statuses),
        offline=sum(status.status_operacional == "offline" for status in statuses),
        com_alerta=sum(status.nivel_alerta in {"amarelo", "vermelho"} for status in statuses),
        # Regra transitória até existir um domínio próprio para suprimentos.
        substituir_toner=sum(
            "substituir toner" in (status.mensagem_alerta or "").casefold()
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
    return _status_to_read(get_printer_status(db, machine_id))


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
