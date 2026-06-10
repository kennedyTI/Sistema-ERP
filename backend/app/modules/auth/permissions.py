"""
Mapeamento dos grupos oficiais para permissoes do portal visual.
"""

from backend.app.modules.auth.schemas import (
    PermissoesImpressoras,
    PermissoesPortal,
    PortalPermissions,
)
from backend.app.modules.printers.permissions import (
    PERMISSOES_EQUIPE_TECNICA,
    PERMISSOES_GESTOR,
    PERMISSOES_IMPRESSORAS,
    PERMISSOES_OPERADOR,
    nome_permissao,
)

GROUP_EQUIPE_TECNICA = "Equipe T\u00e9cnica"
GROUP_GESTOR = "Gestor"
GROUP_OPERADOR = "Operador"
GROUP_INTEGRACAO_PROTHEUS = "Integra\u00e7\u00e3o Protheus"


def portal_permissions_from_django(
    permission_names: set[str],
    *,
    groups: list[str],
    is_superuser: bool = False,
    can_access_admin: bool = False,
) -> tuple[PortalPermissions, PermissoesPortal]:
    enabled = {
        codename: is_superuser or nome_permissao(codename) in permission_names
        for codename in PERMISSOES_IMPRESSORAS
    }
    printer_permissions = PermissoesImpressoras(**enabled)
    can_access_printers = any(
        (
            printer_permissions.ver_dashboard,
            printer_permissions.ver_status,
            printer_permissions.ver_maquinas,
            printer_permissions.ver_papel,
        )
    )
    legacy = PortalPermissions(
        can_access_portal=can_access_printers,
        can_access_admin=can_access_admin,
        can_access_printers=can_access_printers,
        can_access_printers_dashboard=printer_permissions.ver_dashboard,
        can_access_printers_status=printer_permissions.ver_status,
        can_manage_printers_status=False,
        can_access_printers_machines=printer_permissions.ver_maquinas,
        can_access_printers_paper=printer_permissions.ver_papel,
    )
    return legacy, PermissoesPortal(impressoras=printer_permissions)


def portal_permissions_for_groups(groups: list[str], *, is_superuser: bool = False) -> PortalPermissions:
    """Compatibilidade para testes e tokens auxiliares sem acesso ao Django ORM."""
    group_set = set(groups)

    if is_superuser or GROUP_EQUIPE_TECNICA in group_set:
        codes = PERMISSOES_EQUIPE_TECNICA
    elif GROUP_GESTOR in group_set:
        codes = PERMISSOES_GESTOR
    elif GROUP_OPERADOR in group_set:
        codes = PERMISSOES_OPERADOR
    else:
        codes = set()

    permission_names = {nome_permissao(codename) for codename in codes}
    legacy, _nested = portal_permissions_from_django(
        permission_names,
        groups=groups,
        is_superuser=is_superuser,
        can_access_admin=is_superuser or GROUP_EQUIPE_TECNICA in group_set,
    )
    return legacy
