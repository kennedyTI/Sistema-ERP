"""Services do cadastro de modelos e maquinas."""

from backend.app.modules.printers.machines.models import PrinterMachine, PrinterModel
from backend.app.modules.printers.machines.schemas import MachineCreate, MachineStatusUpdate, MachineUpdate
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session


class MachineNotFoundError(Exception):
    pass


class DuplicateMachineIpError(Exception):
    pass


class MachineModelRequiredError(Exception):
    pass


MACHINE_FIELDS = {"name", "ip_address", "sector", "cost_center", "is_active", "notes"}
MODEL_FIELDS = {"manufacturer", "model", "type", "color_mode"}


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
        .options(joinedload(PrinterMachine.printer_model))
        .filter(PrinterMachine.id == machine_id)
        .one_or_none()
    )
    if machine is None:
        raise MachineNotFoundError
    return machine


def _ensure_unique_ip(db: Session, ip_address: str, *, ignore_machine_id: int | None = None) -> None:
    query = db.query(PrinterMachine).filter(PrinterMachine.ip_address == ip_address)
    if ignore_machine_id is not None:
        query = query.filter(PrinterMachine.id != ignore_machine_id)
    if query.first() is not None:
        raise DuplicateMachineIpError


def _get_or_create_printer_model(
    db: Session,
    *,
    manufacturer: str | None,
    model_name: str | None,
    model_type: str | None = None,
    color_mode: str | None = None,
) -> PrinterModel | None:
    if not manufacturer and not model_name:
        return None
    if not manufacturer or not model_name:
        raise MachineModelRequiredError

    printer_model = (
        db.query(PrinterModel)
        .filter(PrinterModel.manufacturer == manufacturer, PrinterModel.name == model_name)
        .one_or_none()
    )

    if printer_model is None:
        printer_model = PrinterModel(
            manufacturer=manufacturer,
            name=model_name,
            type=model_type,
            color_mode=color_mode,
        )
        db.add(printer_model)
        db.flush()
        return printer_model

    if model_type is not None:
        printer_model.type = model_type
    if color_mode is not None:
        printer_model.color_mode = color_mode

    return printer_model


def _apply_machine_fields(machine: PrinterMachine, changes: dict) -> None:
    for field, value in changes.items():
        if field in MACHINE_FIELDS:
            setattr(machine, field, value)


def create_machine(db: Session, payload: MachineCreate) -> PrinterMachine:
    _ensure_unique_ip(db, payload.ip_address)
    data = payload.model_dump()
    printer_model = _get_or_create_printer_model(
        db,
        manufacturer=data.get("manufacturer"),
        model_name=data.get("model"),
        model_type=data.get("type"),
        color_mode=data.get("color_mode"),
    )
    machine_data = {field: value for field, value in data.items() if field in MACHINE_FIELDS}
    machine = PrinterMachine(**machine_data, printer_model=printer_model)
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine


def update_machine(db: Session, machine_id: int, payload: MachineUpdate) -> PrinterMachine:
    machine = get_machine(db, machine_id)
    changes = payload.model_dump(exclude_unset=True)

    if "ip_address" in changes and changes["ip_address"] != machine.ip_address:
        _ensure_unique_ip(db, changes["ip_address"], ignore_machine_id=machine_id)

    if any(field in changes for field in MODEL_FIELDS):
        printer_model = _get_or_create_printer_model(
            db,
            manufacturer=changes.get("manufacturer", machine.manufacturer),
            model_name=changes.get("model", machine.model),
            model_type=changes.get("type", machine.type),
            color_mode=changes.get("color_mode", machine.color_mode),
        )
        machine.printer_model = printer_model
        machine.model_id = printer_model.id if printer_model else None

    _apply_machine_fields(machine, changes)

    db.commit()
    db.refresh(machine)
    return machine


def update_machine_status(db: Session, machine_id: int, payload: MachineStatusUpdate) -> PrinterMachine:
    machine = get_machine(db, machine_id)
    machine.is_active = payload.is_active
    db.commit()
    db.refresh(machine)
    return machine
