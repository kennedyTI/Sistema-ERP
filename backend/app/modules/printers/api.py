"""Router agregado do modulo Impressoras."""

from fastapi import APIRouter

from backend.app.modules.printers.dashboard.api import router as dashboard_router
from backend.app.modules.printers.machines.api import router as machines_router
from backend.app.modules.printers.paper.api import router as paper_router

router = APIRouter(prefix="/printers")
router.include_router(dashboard_router)
router.include_router(machines_router)
router.include_router(paper_router)
