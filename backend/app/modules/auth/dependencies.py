"""
Dependencias FastAPI para JWT e permissoes do portal.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.core.security import TokenError, decode_access_token
from backend.app.core.database import get_db
from backend.app.modules.auth.schemas import PortalUser
from backend.app.modules.auth.services import record_auth_event

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> PortalUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Token de autenticacao ausente.")

    try:
        payload = decode_access_token(credentials.credentials)
        return PortalUser.model_validate(payload["user"])
    except TokenError as exc:
        raise HTTPException(status_code=401, detail="Token de autenticacao invalido ou expirado.") from exc


def require_permission(permission_key: str) -> Callable:
    def dependency(
        request: Request,
        user: PortalUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> PortalUser:
        if getattr(user.permissions, permission_key):
            return user

        try:
            record_auth_event(
                db,
                event="access_denied",
                username=user.username,
                message=f"Acesso negado ao recurso {request.url.path}.",
                success=False,
                extra={"path": request.url.path, "permission": permission_key},
            )
            db.commit()
        except Exception:
            rollback = getattr(db, "rollback", None)
            if rollback:
                rollback()

        raise HTTPException(status_code=403, detail="Acesso nao autorizado.")

    return dependency


require_portal_access = require_permission("can_access_portal")
require_admin_access = require_permission("can_access_admin")

