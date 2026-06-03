"""
Mapeamento dos grupos oficiais para permissoes do portal visual.
"""

from backend.app.modules.auth.schemas import PortalPermissions

GROUP_EQUIPE_TECNICA = "Equipe T\u00e9cnica"
GROUP_GESTOR = "Gestor"
GROUP_OPERADOR = "Operador"
GROUP_INTEGRACAO_PROTHEUS = "Integra\u00e7\u00e3o Protheus"

def portal_permissions_for_groups(groups: list[str], *, is_superuser: bool = False) -> PortalPermissions:
    group_set = set(groups)

    if is_superuser or GROUP_EQUIPE_TECNICA in group_set:
        return PortalPermissions(
            can_access_portal=True,
            can_access_admin=True,
            can_access_printers=True,
            can_access_printers_dashboard=True,
            can_access_printers_machines=True,
            can_access_printers_paper=True,
        )

    if GROUP_GESTOR in group_set:
        return PortalPermissions(
            can_access_portal=True,
            can_access_printers=True,
            can_access_printers_dashboard=True,
            can_access_printers_machines=True,
            can_access_printers_paper=True,
        )

    if GROUP_OPERADOR in group_set:
        return PortalPermissions(
            can_access_portal=True,
            can_access_printers=True,
            can_access_printers_dashboard=True,
            can_access_printers_machines=True,
        )

    return PortalPermissions()
