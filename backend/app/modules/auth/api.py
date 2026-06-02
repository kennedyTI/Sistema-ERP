"""
Rotas de autenticacao do portal React.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.security import create_access_token
from backend.app.core.database import get_db
from backend.app.modules.auth.dependencies import get_current_user
from backend.app.modules.auth.schemas import LoginRequest, LoginResponse, LogoutResponse, PortalUser
from backend.app.modules.auth.services import authenticate_django_user, record_auth_event

router = APIRouter(prefix="/auth", tags=["Auth"])


def _rollback_safely(db: Session) -> None:
    rollback = getattr(db, "rollback", None)
    if rollback:
        rollback()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_django_user(payload.username, payload.password)

    if user is None:
        try:
            record_auth_event(
                db,
                event="login_failed",
                username=payload.username,
                message="Tentativa de login recusada.",
                success=False,
            )
            db.commit()
        except Exception:
            _rollback_safely(db)
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos.")

    try:
        record_auth_event(
            db,
            event="login_success",
            username=user.username,
            message="Login realizado com sucesso.",
            success=True,
            extra={"groups": user.groups},
        )
        db.commit()
    except Exception:
        _rollback_safely(db)

    return LoginResponse(access_token=create_access_token(user), user=user)


@router.get("/me", response_model=PortalUser)
def me(user: PortalUser = Depends(get_current_user)):
    return user


@router.post("/logout", response_model=LogoutResponse)
def logout(
    user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        record_auth_event(
            db,
            event="logout",
            username=user.username,
            message="Logout registrado pelo portal.",
            success=True,
        )
        db.commit()
    except Exception:
        _rollback_safely(db)

    return LogoutResponse()

