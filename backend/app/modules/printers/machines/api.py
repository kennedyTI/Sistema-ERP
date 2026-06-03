"""Rotas iniciais de maquinas do modulo Impressoras."""

from fastapi import APIRouter, Depends

from backend.app.core.response import ApiResponse, api_success
from backend.app.modules.auth.dependencies import require_printers_machines_access
from backend.app.modules.auth.schemas import PortalUser
from backend.app.modules.printers.machines.schemas import MachineRead
from backend.app.modules.printers.machines.services import list_machines

router = APIRouter(prefix="/machines", tags=["Impressoras - Maquinas"])


@router.get("", response_model=ApiResponse[list[MachineRead]])
def machines_list(
    _user: PortalUser = Depends(require_printers_machines_access),
):
    machines = [MachineRead.model_validate(machine) for machine in list_machines()]
    return api_success(machines, "Lista inicial de maquinas.")
