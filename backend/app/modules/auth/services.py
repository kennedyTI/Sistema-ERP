"""
Service Layer de autenticacao do portal.

Usa Django Auth como fonte de identidade e traduz grupos oficiais para
permissoes minimas da base v2 limpa.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.django import ensure_django_ready
from backend.app.modules.audit.orm import Log
from backend.app.modules.audit.services import create_audit_log
from backend.app.modules.auth.permissions import portal_permissions_for_groups
from backend.app.modules.auth.schemas import PortalUser

logger = logging.getLogger(__name__)

def build_portal_user(django_user: Any) -> PortalUser:
    groups = list(django_user.groups.values_list("name", flat=True))
    display_name = ""
    if hasattr(django_user, "get_full_name"):
        display_name = django_user.get_full_name()
    display_name = display_name or getattr(django_user, "username", "")

    return PortalUser(
        username=django_user.username,
        display_name=display_name,
        email=getattr(django_user, "email", "") or None,
        groups=groups,
        permissions=portal_permissions_for_groups(
            groups,
            is_superuser=bool(getattr(django_user, "is_superuser", False)),
        ),
    )


def authenticate_django_user(username: str, password: str) -> PortalUser | None:
    ensure_django_ready()

    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    user = user_model.objects.filter(username=username, is_active=True).first()
    if user is None or not user.check_password(password):
        return None

    return build_portal_user(user)


def record_auth_event(
    db: Session,
    *,
    event: str,
    username: str | None,
    message: str,
    success: bool | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    safe_username = username or "anonymous"
    payload = {
        "event": event,
        "username": safe_username,
        "success": success,
        **(extra or {}),
    }

    logger.info("auth_event", extra=payload)
    db.add(
        Log(
            tipo=event,
            message=message,
            valor_anterior=None,
            valor_novo=f"usuario={safe_username}; sucesso={success}",
        )
    )
    create_audit_log(
        db,
        table_name="auth_events",
        record_id=None,
        action="manual_fix",
        old_data=None,
        new_data=payload,
        changed_by=safe_username,
        source="api_internal",
    )

