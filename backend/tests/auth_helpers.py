from backend.app.core.security import create_access_token
from backend.app.modules.auth.schemas import PortalPermissions, PortalUser


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
) -> PortalUser:
    return PortalUser(
        username=username,
        display_name=username,
        email=f"{username}@example.com",
        groups=groups or ["Equipe T\u00e9cnica"],
        permissions=PortalPermissions(
            can_access_portal=portal,
            can_access_admin=admin,
            can_access_printers=printers,
            can_access_printers_dashboard=printers_dashboard,
            can_access_printers_status=printers_status,
            can_manage_printers_status=printers_status_manage,
            can_access_printers_machines=printers_machines,
            can_access_printers_paper=printers_paper,
        ),
    )


def auth_headers(**kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(make_user(**kwargs))}"}

