"""Dependencias de permissao da API de rastreabilidade."""

from backend.app.modules.auth.dependencies import (
    require_compras_rastreabilidade_update,
    require_compras_rastreabilidade_view,
)


__all__ = (
    "require_compras_rastreabilidade_update",
    "require_compras_rastreabilidade_view",
)
