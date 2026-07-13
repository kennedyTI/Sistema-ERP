"""
Mapeamento dos grupos oficiais para permissoes do portal visual.
"""

from backend.app.modules.auth.schemas import (
    PermissoesCompras,
    PermissoesImpressoras,
    PermissoesPortal,
    PortalPermissions,
)
from backend.app.modules.compras.permissions import (
    PERMISSOES_COMPRAS,
    PERMISSOES_COMPRAS_EQUIPE_TECNICA,
    PERMISSOES_COMPRAS_GESTOR,
    PERMISSOES_COMPRAS_OPERADOR,
    nome_permissao as nome_permissao_compras,
)
from backend.app.modules.printers.permissions import (
    PERMISSOES_EQUIPE_TECNICA,
    PERMISSOES_GESTOR,
    PERMISSOES_IMPRESSORAS,
    PERMISSOES_OPERADOR,
    nome_permissao as nome_permissao_impressoras,
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
        codename: is_superuser or nome_permissao_impressoras(codename) in permission_names
        for codename in PERMISSOES_IMPRESSORAS
    }
    printer_permissions = PermissoesImpressoras(**enabled)
    compras_enabled = {
        codename: is_superuser or nome_permissao_compras(codename) in permission_names
        for codename in PERMISSOES_COMPRAS
    }
    compras_permissions = PermissoesCompras(**compras_enabled)
    can_access_printers = any(
        (
            printer_permissions.ver_dashboard,
            printer_permissions.ver_status,
            printer_permissions.ver_maquinas,
            printer_permissions.ver_papel,
        )
    )
    can_access_compras = compras_permissions.ver_rastreabilidade
    legacy = PortalPermissions(
        can_access_portal=can_access_printers or can_access_compras,
        can_access_admin=can_access_admin,
        can_access_printers=can_access_printers,
        can_access_printers_dashboard=printer_permissions.ver_dashboard,
        can_access_printers_status=printer_permissions.ver_status,
        can_manage_printers_status=False,
        can_access_printers_machines=printer_permissions.ver_maquinas,
        can_access_printers_paper=printer_permissions.ver_papel,
        can_access_compras=can_access_compras,
        can_access_compras_rastreabilidade=compras_permissions.ver_rastreabilidade,
        can_manage_compras_rastreabilidade=compras_permissions.atualizar_rastreabilidade,
    )
    return legacy, PermissoesPortal(
        impressoras=printer_permissions,
        compras=compras_permissions,
    )


def portal_permissions_for_groups(groups: list[str], *, is_superuser: bool = False) -> PortalPermissions:
    """Compatibilidade para testes e tokens auxiliares sem acesso ao Django ORM."""
    group_set = set(groups)

    if is_superuser or GROUP_EQUIPE_TECNICA in group_set:
        printer_codes = PERMISSOES_EQUIPE_TECNICA
        compras_codes = PERMISSOES_COMPRAS_EQUIPE_TECNICA
    elif GROUP_GESTOR in group_set:
        printer_codes = PERMISSOES_GESTOR
        compras_codes = PERMISSOES_COMPRAS_GESTOR
    elif GROUP_OPERADOR in group_set:
        printer_codes = PERMISSOES_OPERADOR
        compras_codes = PERMISSOES_COMPRAS_OPERADOR
    else:
        printer_codes = set()
        compras_codes = set()

    permission_names = {
        *(nome_permissao_impressoras(codename) for codename in printer_codes),
        *(nome_permissao_compras(codename) for codename in compras_codes),
    }
    legacy, _nested = portal_permissions_from_django(
        permission_names,
        groups=groups,
        is_superuser=is_superuser,
        can_access_admin=is_superuser or GROUP_EQUIPE_TECNICA in group_set,
    )
    return legacy
