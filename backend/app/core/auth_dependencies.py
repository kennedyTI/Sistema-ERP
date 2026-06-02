"""
Compatibilidade para imports comuns de autenticacao.
"""

from backend.app.modules.auth.dependencies import (  # noqa: F401
    get_current_user,
    require_admin_access,
    require_permission,
    require_portal_access,
)
