"""Agregador de rotas do modulo Compras."""

from fastapi import APIRouter

from backend.app.modules.compras.rastreabilidade.api import router as rastreabilidade_router


router = APIRouter(prefix="/compras")
router.include_router(rastreabilidade_router)
