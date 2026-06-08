"""
Compatibilidade para imports comuns de autenticacao.
"""

from backend.app.modules.auth.dependencies import (  # noqa: F401
    get_current_user,
    require_admin_access,
    require_permission,
    require_portal_access,
    require_printers_access,
    require_printers_dashboard_access,
    require_printers_machines_access,
    require_printers_paper_access,
)
