"""
Schemas da autenticacao do portal React.
"""

from pydantic import BaseModel, Field


class PermissoesImpressoras(BaseModel):
    ver_dashboard: bool = False
    ver_status: bool = False
    ver_maquinas: bool = False
    criar_maquinas: bool = False
    editar_maquinas: bool = False
    alternar_status_maquinas: bool = False
    ver_papel: bool = False


class PermissoesPortal(BaseModel):
    impressoras: PermissoesImpressoras = Field(default_factory=PermissoesImpressoras)


class UsuarioAutenticado(BaseModel):
    id: int | None = None
    username: str
    grupos: list[str] = Field(default_factory=list)


class PortalPermissions(BaseModel):
    can_access_portal: bool = False
    can_access_admin: bool = False
    can_access_printers: bool = False
    can_access_printers_dashboard: bool = False
    can_access_printers_status: bool = False
    can_manage_printers_status: bool = False
    can_access_printers_machines: bool = False
    can_access_printers_paper: bool = False


class PortalUser(BaseModel):
    id: int | None = None
    username: str
    display_name: str
    email: str | None = None
    groups: list[str] = Field(default_factory=list)
    permissions: PortalPermissions = Field(default_factory=PortalPermissions)
    usuario: UsuarioAutenticado | None = None
    permissoes: PermissoesPortal = Field(default_factory=PermissoesPortal)


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
