"""Rota de status do dashboard de Impressoras."""

from fastapi import APIRouter, Depends

from backend.app.core.response import ApiResponse, api_success
from backend.app.modules.auth.dependencies import require_printers_dashboard_access
from backend.app.modules.auth.schemas import PortalUser
from backend.app.modules.printers.dashboard.schemas import DashboardStatus
from backend.app.modules.printers.dashboard.services import get_dashboard_status

router = APIRouter(prefix="/dashboard", tags=["Impressoras - Dashboard"])


@router.get("", response_model=ApiResponse[DashboardStatus])
def dashboard_status(
    _user: PortalUser = Depends(require_printers_dashboard_access),
):
    status = get_dashboard_status()
    return api_success(status, "Dashboard de impressoras em desenvolvimento.")
