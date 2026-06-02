"""
Schemas da autenticacao do portal React.
"""

from pydantic import BaseModel, Field


class PortalPermissions(BaseModel):
    can_access_portal: bool = False
    can_access_admin: bool = False


class PortalUser(BaseModel):
    username: str
    display_name: str
    email: str | None = None
    groups: list[str] = Field(default_factory=list)
    permissions: PortalPermissions = Field(default_factory=PortalPermissions)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: PortalUser


class LogoutResponse(BaseModel):
    success: bool = True
    message: str = "Logout registrado com sucesso."
