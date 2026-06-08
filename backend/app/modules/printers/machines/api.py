"""Rotas CRUD de maquinas do modulo Impressoras."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.response import ApiResponse, api_success
from backend.app.modules.auth.dependencies import require_printers_machines_access
from backend.app.modules.auth.schemas import PortalUser
from backend.app.modules.printers.machines.schemas import MachineCreate, MachineRead, MachineStatusUpdate, MachineUpdate
from backend.app.modules.printers.machines.services import (
    DuplicateMachineIpError,
    MachineNotFoundError,
    create_machine,
    get_machine,
    list_machines,
    update_machine,
    update_machine_status,
)

router = APIRouter(prefix="/machines", tags=["Impressoras - Maquinas"])


@router.get("", response_model=ApiResponse[list[MachineRead]])
def machines_list(
    _user: PortalUser = Depends(require_printers_machines_access),
    db: Session = Depends(get_db),
):
    machines = [MachineRead.model_validate(machine) for machine in list_machines(db)]
    return api_success(machines, "Lista de maquinas.")


@router.post("", response_model=ApiResponse[MachineRead], status_code=status.HTTP_201_CREATED)
def machines_create(
    payload: MachineCreate,
    _user: PortalUser = Depends(require_printers_machines_access),
    db: Session = Depends(get_db),
):
    try:
        machine = create_machine(db, payload)
    except DuplicateMachineIpError as exc:
        raise HTTPException(status_code=409, detail="Ja existe uma maquina cadastrada com este IP.") from exc

    return api_success(MachineRead.model_validate(machine), "Maquina cadastrada.")


@router.get("/{machine_id}", response_model=ApiResponse[MachineRead])
def machines_detail(
    machine_id: int,
    _user: PortalUser = Depends(require_printers_machines_access),
    db: Session = Depends(get_db),
):
    try:
        machine = get_machine(db, machine_id)
    except MachineNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Maquina nao encontrada.") from exc

    return api_success(MachineRead.model_validate(machine), "Maquina encontrada.")


@router.patch("/{machine_id}", response_model=ApiResponse[MachineRead])
def machines_update(
    machine_id: int,
    payload: MachineUpdate,
    _user: PortalUser = Depends(require_printers_machines_access),
    db: Session = Depends(get_db),
):
    try:
        machine = update_machine(db, machine_id, payload)
    except MachineNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Maquina nao encontrada.") from exc
    except DuplicateMachineIpError as exc:
        raise HTTPException(status_code=409, detail="Ja existe uma maquina cadastrada com este IP.") from exc

    return api_success(MachineRead.model_validate(machine), "Maquina atualizada.")


@router.patch("/{machine_id}/status", response_model=ApiResponse[MachineRead])
def machines_status_update(
    machine_id: int,
    payload: MachineStatusUpdate,
    _user: PortalUser = Depends(require_printers_machines_access),
    db: Session = Depends(get_db),
):
    try:
        machine = update_machine_status(db, machine_id, payload)
    except MachineNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Maquina nao encontrada.") from exc

    message = "Maquina ativada." if machine.is_active else "Maquina inativada."
    return api_success(MachineRead.model_validate(machine), message)
