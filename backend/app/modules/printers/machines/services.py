"""Services do cadastro de maquinas."""

from backend.app.modules.printers.machines.models import PrinterMachine
from backend.app.modules.printers.machines.schemas import MachineCreate, MachineStatusUpdate, MachineUpdate
from sqlalchemy.orm import Session


class MachineNotFoundError(Exception):
    pass


class DuplicateMachineIpError(Exception):
    pass


def list_machines(db: Session) -> list[PrinterMachine]:
    return db.query(PrinterMachine).order_by(PrinterMachine.name.asc(), PrinterMachine.id.asc()).all()


def get_machine(db: Session, machine_id: int) -> PrinterMachine:
    machine = db.get(PrinterMachine, machine_id)
    if machine is None:
        raise MachineNotFoundError
    return machine


def _ensure_unique_ip(db: Session, ip_address: str, *, ignore_machine_id: int | None = None) -> None:
    query = db.query(PrinterMachine).filter(PrinterMachine.ip_address == ip_address)
    if ignore_machine_id is not None:
        query = query.filter(PrinterMachine.id != ignore_machine_id)
    if query.first() is not None:
        raise DuplicateMachineIpError


def create_machine(db: Session, payload: MachineCreate) -> PrinterMachine:
    _ensure_unique_ip(db, payload.ip_address)
    machine = PrinterMachine(**payload.model_dump())
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine


def update_machine(db: Session, machine_id: int, payload: MachineUpdate) -> PrinterMachine:
    machine = get_machine(db, machine_id)
    changes = payload.model_dump(exclude_unset=True)

    if "ip_address" in changes and changes["ip_address"] != machine.ip_address:
        _ensure_unique_ip(db, changes["ip_address"], ignore_machine_id=machine_id)

    for field, value in changes.items():
        setattr(machine, field, value)

    db.commit()
    db.refresh(machine)
    return machine


def update_machine_status(db: Session, machine_id: int, payload: MachineStatusUpdate) -> PrinterMachine:
    machine = get_machine(db, machine_id)
    machine.is_active = payload.is_active
    db.commit()
    db.refresh(machine)
    return machine
