"""Regras transacionais do cadastro de maquinas do modulo Impressoras."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import distinct, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.app.core.timezone import now_sao_paulo
from backend.app.modules.audit.services import create_audit_log
from backend.app.modules.printers.machines.models import PrinterMachine, PrinterModel
from backend.app.modules.printers.machines.schemas import (
    AcoesMaquina,
    DetalhesMaquina,
    LogOperacionalRead,
    MaquinaCreate,
    MaquinaRead,
    MaquinaStatusUpdate,
    MaquinaUpdate,
    ModeloImpressoraRead,
    ResumoMaquinas,
    ResultadoToggleMaquina,
    StatusOperacionalResumo,
)
from backend.app.modules.printers.status.models import LogImpressora, StatusImpressora


class MachineNotFoundError(Exception):
    pass


class PrinterModelNotFoundError(Exception):
    pass


class MachineConflictError(Exception):
    pass


class MachineValidationError(Exception):
    def __init__(self, errors: dict[str, list[str]]):
        super().__init__("Dados invalidos para a maquina.")
        self.errors = errors


def list_machines(db: Session) -> list[PrinterMachine]:
    return (
        db.query(PrinterMachine)
        .options(joinedload(PrinterMachine.printer_model))
        .order_by(PrinterMachine.name.asc(), PrinterMachine.id.asc())
        .all()
    )


def get_machine(db: Session, machine_id: int) -> PrinterMachine:
    machine = (
        db.query(PrinterMachine)
        .options(
            joinedload(PrinterMachine.printer_model),
            joinedload(PrinterMachine.status_operacional_atual),
        )
        .filter(PrinterMachine.id == machine_id)
        .one_or_none()
    )
    if machine is None:
        raise MachineNotFoundError
    return machine


def machine_to_read(machine: PrinterMachine) -> MaquinaRead:
    model = machine.printer_model
    return MaquinaRead(
        id=machine.id,
        nome=machine.name,
        endereco_ip=machine.ip_address,
        modelo_id=machine.model_id,
        fabricante=model.manufacturer if model else None,
        modelo=model.name if model else None,
        tipo=model.type if model else None,
        cor_modelo=model.color_mode if model else None,
        setor=machine.sector,
        centro_custo=machine.cost_center,
        ativo=machine.is_active,
        observacoes=machine.notes,
        url_imagem=model.url_imagem if model else None,
        criado_em=machine.created_at,
        atualizado_em=machine.updated_at,
    )


def summarize_machines(db: Session) -> ResumoMaquinas:
    total = db.query(func.count(PrinterMachine.id)).scalar() or 0
    active = (
        db.query(func.count(PrinterMachine.id))
        .filter(PrinterMachine.is_active.is_(True))
        .scalar()
        or 0
    )
    manufacturers = (
        db.query(func.count(distinct(PrinterModel.manufacturer)))
        .join(PrinterMachine, PrinterMachine.model_id == PrinterModel.id)
        .scalar()
        or 0
    )
    models = db.query(func.count(PrinterModel.id)).scalar() or 0
    return ResumoMaquinas(
        total_maquinas=total,
        ativas=active,
        inativas=total - active,
        fabricantes=manufacturers,
        modelos_cadastrados=models,
    )


def _model_to_read(model: PrinterModel | None) -> ModeloImpressoraRead | None:
    if model is None:
        return None
    return ModeloImpressoraRead(
        id=model.id,
        fabricante=model.manufacturer,
        modelo=model.name,
        tipo=model.type,
        cor_modelo=model.color_mode,
        url_imagem=model.url_imagem,
    )


def read_machine_details(
    db: Session,
    machine_id: int,
    *,
    can_edit: bool,
    can_toggle_status: bool,
    log_limit: int = 20,
) -> DetalhesMaquina:
    machine = get_machine(db, machine_id)
    status = machine.status_operacional_atual
    logs = (
        db.query(LogImpressora)
        .filter(LogImpressora.maquina_id == machine_id)
        .order_by(LogImpressora.criado_em.desc(), LogImpressora.id.desc())
        .limit(log_limit)
        .all()
    )
    status_read = None
    if status is not None:
        status_read = StatusOperacionalResumo(
            status=status.status_operacional,
            alerta=status.mensagem_alerta,
            mensagem=status.mensagem_operador,
            ultima_verificacao_em=status.ultima_verificacao_em,
        )

    return DetalhesMaquina(
        maquina=machine_to_read(machine),
        modelo_dados=_model_to_read(machine.printer_model),
        status_operacional=status_read,
        logs_recentes=[
            LogOperacionalRead(
                id=log.id,
                tipo_evento=log.tipo_evento,
                status_anterior=log.status_anterior,
                status_novo=log.status_novo,
                alerta_anterior=log.alerta_anterior,
                alerta_novo=log.alerta_novo,
                mensagem=log.mensagem,
                verificado_em=log.verificado_em,
                origem=log.origem,
            )
            for log in logs
        ],
        acoes=AcoesMaquina(
            pode_editar=can_edit,
            pode_alternar_status=can_toggle_status,
        ),
    )


def _get_model(db: Session, model_id: int) -> PrinterModel:
    model = db.query(PrinterModel).filter(PrinterModel.id == model_id).one_or_none()
    if model is None:
        raise PrinterModelNotFoundError
    return model


def _get_or_create_legacy_model(db: Session, payload: MaquinaCreate) -> PrinterModel:
    if payload.modelo_id is not None:
        return _get_model(db, payload.modelo_id)

    model = (
        db.query(PrinterModel)
        .filter(
            PrinterModel.manufacturer == payload.fabricante,
            PrinterModel.name == payload.modelo,
        )
        .one_or_none()
    )
    if model is not None:
        return model

    model = PrinterModel(
        manufacturer=payload.fabricante,
        name=payload.modelo,
        type=payload.tipo,
        color_mode=payload.cor_modelo,
    )
    db.add(model)
    db.flush()
    return model


def _ensure_unique_ip(
    db: Session,
    ip_address_value: str,
    *,
    ignore_machine_id: int | None = None,
) -> None:
    query = db.query(PrinterMachine).filter(PrinterMachine.ip_address == ip_address_value)
    if ignore_machine_id is not None:
        query = query.filter(PrinterMachine.id != ignore_machine_id)
    if query.first() is not None:
        raise MachineValidationError(
            {"endereco_ip": ["Este IP ja esta cadastrado para outra maquina."]}
        )


def _machine_snapshot(machine: PrinterMachine) -> dict:
    return machine_to_read(machine).model_dump(mode="json")


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def create_machine(
    db: Session,
    payload: MaquinaCreate,
    *,
    changed_by: str,
) -> PrinterMachine:
    from backend.app.modules.printers.status.services import create_initial_status

    try:
        _ensure_unique_ip(db, payload.endereco_ip)
        model = _get_or_create_legacy_model(db, payload)
        machine = PrinterMachine(
            name=payload.nome,
            ip_address=payload.endereco_ip,
            printer_model=model,
            sector=payload.setor,
            cost_center=payload.centro_custo,
            is_active=payload.ativo,
            notes=payload.observacoes,
        )
        db.add(machine)
        db.flush()
        create_initial_status(db, machine.id)
        db.flush()
        create_audit_log(
            db,
            table_name="printer_machines",
            record_id=machine.id,
            action="create",
            old_data=None,
            new_data=_machine_snapshot(machine),
            changed_by=changed_by,
            source="api_internal",
        )
        db.commit()
        return get_machine(db, machine.id)
    except (MachineValidationError, PrinterModelNotFoundError):
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise MachineValidationError(
            {"endereco_ip": ["Este IP ja esta cadastrado para outra maquina."]}
        ) from exc
    except Exception:
        db.rollback()
        raise


def update_machine(
    db: Session,
    machine_id: int,
    payload: MaquinaUpdate,
    *,
    changed_by: str,
) -> PrinterMachine:
    machine = get_machine(db, machine_id)
    expected_updated_at = _normalize_timestamp(payload.atualizado_em)
    current_updated_at = _normalize_timestamp(machine.updated_at)
    if expected_updated_at != current_updated_at:
        raise MachineConflictError

    changes = payload.model_dump(exclude_unset=True, exclude={"atualizado_em"})
    if not changes:
        return machine

    if "nome" in changes and not changes["nome"]:
        raise MachineValidationError({"nome": ["O nome da maquina e obrigatorio."]})
    if "endereco_ip" in changes:
        if not changes["endereco_ip"]:
            raise MachineValidationError(
                {"endereco_ip": ["O endereco IP da maquina e obrigatorio."]}
            )
        if changes["endereco_ip"] != machine.ip_address:
            _ensure_unique_ip(
                db,
                changes["endereco_ip"],
                ignore_machine_id=machine_id,
            )
    if "modelo_id" in changes:
        if changes["modelo_id"] is None:
            raise MachineValidationError({"modelo_id": ["O modelo e obrigatorio."]})
        model = _get_model(db, changes["modelo_id"])
    else:
        model = machine.printer_model
    if model is None:
        raise MachineValidationError({"modelo_id": ["O modelo e obrigatorio."]})

    old_data = _machine_snapshot(machine)
    field_map = {
        "nome": "name",
        "endereco_ip": "ip_address",
        "setor": "sector",
        "centro_custo": "cost_center",
        "observacoes": "notes",
    }
    try:
        for contract_field, model_field in field_map.items():
            if contract_field in changes:
                setattr(machine, model_field, changes[contract_field])
        machine.printer_model = model
        machine.model_id = model.id
        machine.updated_at = now_sao_paulo()
        db.flush()
        new_data = _machine_snapshot(machine)
        changed_fields = {
            field: {"anterior": old_data.get(field), "novo": new_data.get(field)}
            for field in new_data
            if old_data.get(field) != new_data.get(field)
        }
        create_audit_log(
            db,
            table_name="printer_machines",
            record_id=machine.id,
            action="update",
            old_data={"maquina": old_data, "campos_alterados": list(changed_fields)},
            new_data={"maquina": new_data, "alteracoes": changed_fields},
            changed_by=changed_by,
            source="api_internal",
        )
        db.commit()
        return get_machine(db, machine.id)
    except (MachineValidationError, PrinterModelNotFoundError):
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise MachineValidationError(
            {"endereco_ip": ["Este IP ja esta cadastrado para outra maquina."]}
        ) from exc
    except Exception:
        db.rollback()
        raise


def update_machine_status(
    db: Session,
    machine_id: int,
    payload: MaquinaStatusUpdate,
    *,
    changed_by: str,
) -> ResultadoToggleMaquina:
    machine = get_machine(db, machine_id)
    old_data = _machine_snapshot(machine)

    try:
        machine.is_active = payload.ativo
        machine.updated_at = now_sao_paulo()
        db.flush()
        new_data = _machine_snapshot(machine)
        create_audit_log(
            db,
            table_name="printer_machines",
            record_id=machine.id,
            action="update",
            old_data={
                "ativo": old_data["ativo"],
                "atualizado_em": old_data["atualizado_em"],
            },
            new_data={
                "ativo": new_data["ativo"],
                "atualizado_em": new_data["atualizado_em"],
            },
            changed_by=changed_by,
            source="api_internal",
        )
        db.commit()
        updated = get_machine(db, machine.id)
        return ResultadoToggleMaquina(
            maquina=machine_to_read(updated),
            resumo=summarize_machines(db),
        )
    except Exception:
        db.rollback()
        raise
