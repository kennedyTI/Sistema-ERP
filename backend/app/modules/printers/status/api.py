"""API de consulta e atualizacao controlada do status operacional."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.response import ApiResponse, api_success
from backend.app.modules.auth.dependencies import require_printers_status_access, require_printers_status_manage
from backend.app.modules.auth.schemas import PortalUser
from backend.app.modules.printers.status.schemas import (
    PrinterLogRead,
    PrinterStatusRead,
    PrinterStatusSummary,
    PrinterStatusUpdate,
)
from backend.app.modules.printers.status.services import (
    PrinterStatusNotFoundError,
    list_printer_logs,
    list_printer_statuses,
    read_printer_status,
    summarize_printer_statuses,
    update_printer_status,
)

router = APIRouter(prefix="/status", tags=["Impressoras - Status"])


@router.get("", response_model=ApiResponse[list[PrinterStatusRead]])
def status_list(
    _user: PortalUser = Depends(require_printers_status_access),
    db: Session = Depends(get_db),
):
    return api_success(list_printer_statuses(db), "Status das impressoras.")


@router.get("/summary", response_model=ApiResponse[PrinterStatusSummary])
def status_summary(
    _user: PortalUser = Depends(require_printers_status_access),
    db: Session = Depends(get_db),
):
    return api_success(summarize_printer_statuses(db), "Resumo operacional das impressoras.")


@router.get("/{machine_id}", response_model=ApiResponse[PrinterStatusRead])
def status_detail(
    machine_id: int,
    _user: PortalUser = Depends(require_printers_status_access),
    db: Session = Depends(get_db),
):
    try:
        data = read_printer_status(db, machine_id)
    except PrinterStatusNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Status da impressora nao encontrado.") from exc
    return api_success(data, "Status da impressora.")


@router.patch("/{machine_id}", response_model=ApiResponse[PrinterStatusRead])
def status_update(
    machine_id: int,
    payload: PrinterStatusUpdate,
    _user: PortalUser = Depends(require_printers_status_manage),
    db: Session = Depends(get_db),
):
    try:
        data = update_printer_status(db, machine_id, payload)
    except PrinterStatusNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Status da impressora nao encontrado.") from exc
    return api_success(data, "Status atualizado manualmente.")


@router.get("/{machine_id}/logs", response_model=ApiResponse[list[PrinterLogRead]])
def status_logs(
    machine_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    _user: PortalUser = Depends(require_printers_status_access),
    db: Session = Depends(get_db),
):
    try:
        data = list_printer_logs(db, machine_id, limit=limit)
    except PrinterStatusNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Status da impressora nao encontrado.") from exc
    return api_success(data, "Logs operacionais da impressora.")
