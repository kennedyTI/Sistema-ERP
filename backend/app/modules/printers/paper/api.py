"""Rota de status do submodulo Papel."""

from fastapi import APIRouter, Depends

from backend.app.core.response import ApiResponse, api_success
from backend.app.modules.auth.dependencies import require_printers_paper_access
from backend.app.modules.auth.schemas import PortalUser
from backend.app.modules.printers.paper.schemas import PaperStatus
from backend.app.modules.printers.paper.services import get_paper_status

router = APIRouter(prefix="/paper", tags=["Impressoras - Papel"])


@router.get("", response_model=ApiResponse[PaperStatus])
def paper_status(
    _user: PortalUser = Depends(require_printers_paper_access),
):
    status = get_paper_status()
    return api_success(status, "Submodulo Papel em desenvolvimento.")
