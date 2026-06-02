from backend.app.core.security import create_access_token
from backend.app.modules.auth.schemas import PortalPermissions, PortalUser


def make_user(
    *,
    username: str = "tester",
    groups: list[str] | None = None,
    portal: bool = True,
    admin: bool = False,
) -> PortalUser:
    return PortalUser(
        username=username,
        display_name=username,
        email=f"{username}@example.com",
        groups=groups or ["Equipe T\u00e9cnica"],
        permissions=PortalPermissions(
            can_access_portal=portal,
            can_access_admin=admin,
        ),
    )


def auth_headers(**kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(make_user(**kwargs))}"}

