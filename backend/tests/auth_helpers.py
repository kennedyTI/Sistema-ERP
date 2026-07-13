from backend.app.core.security import create_access_token
from backend.app.modules.auth.schemas import (
    PermissoesCompras,
    PermissoesImpressoras,
    PermissoesPortal,
    PortalPermissions,
    PortalUser,
    UsuarioAutenticado,
)


def make_user(
    *,
    username: str = "tester",
    groups: list[str] | None = None,
    portal: bool = True,
    admin: bool = False,
    printers: bool = False,
    printers_dashboard: bool = False,
    printers_status: bool = False,
    printers_status_manage: bool = False,
    printers_machines: bool = False,
    printers_paper: bool = False,
    printers_machines_create: bool | None = None,
    printers_machines_edit: bool | None = None,
    printers_machines_toggle: bool | None = None,
    compras_rastreabilidade: bool = False,
    compras_rastreabilidade_update: bool | None = None,
) -> PortalUser:
    groups = groups or ["Equipe T\u00e9cnica"]
    create_allowed = printers_machines if printers_machines_create is None else printers_machines_create
    edit_allowed = printers_machines if printers_machines_edit is None else printers_machines_edit
    toggle_allowed = printers_machines if printers_machines_toggle is None else printers_machines_toggle
    compras_update_allowed = (
        compras_rastreabilidade
        if compras_rastreabilidade_update is None
        else compras_rastreabilidade_update
    )
    return PortalUser(
        id=1,
        username=username,
        display_name=username,
        email=f"{username}@example.com",
        groups=groups,
        permissions=PortalPermissions(
            can_access_portal=portal,
            can_access_admin=admin,
            can_access_printers=printers,
            can_access_printers_dashboard=printers_dashboard,
            can_access_printers_status=printers_status,
            can_manage_printers_status=printers_status_manage,
            can_access_printers_machines=printers_machines,
            can_access_printers_paper=printers_paper,
            can_access_compras=compras_rastreabilidade,
            can_access_compras_rastreabilidade=compras_rastreabilidade,
            can_manage_compras_rastreabilidade=compras_update_allowed,
        ),
        usuario=UsuarioAutenticado(id=1, username=username, grupos=groups),
        permissoes=PermissoesPortal(
            impressoras=PermissoesImpressoras(
                ver_dashboard=printers_dashboard,
                ver_status=printers_status,
                ver_maquinas=printers_machines,
                criar_maquinas=create_allowed,
                editar_maquinas=edit_allowed,
                alternar_status_maquinas=toggle_allowed,
                ver_papel=printers_paper,
            ),
            compras=PermissoesCompras(
                ver_rastreabilidade=compras_rastreabilidade,
                atualizar_rastreabilidade=compras_update_allowed,
            ),
        ),
    )


def auth_headers(**kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(make_user(**kwargs))}"}

