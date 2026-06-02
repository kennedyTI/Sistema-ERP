"""
JWT HS256 minimo para o MVP de login do portal.

Mantem o projeto sem dependencia extra de JWT e concentra a assinatura em um
unico modulo para facilitar a troca futura por outro provedor/autenticador.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from backend.app.modules.auth.schemas import PortalUser


class TokenError(Exception):
    """Erro de validacao/assinatura/expiracao do token."""


def _jwt_secret() -> str:
    return (
        os.getenv("JWT_SECRET_KEY")
        or os.getenv("DJANGO_SECRET_KEY")
        or "dev-only-jwt-secret-key-change-in-production"
    )


def _jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")


def _jwt_expire_minutes() -> int:
    raw_value = os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "480")
    try:
        return max(1, int(raw_value))
    except (TypeError, ValueError):
        return 480


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except Exception as exc:  # pragma: no cover - defesa contra payload malformado
        raise TokenError("Token invalido") from exc


def _json_dumps(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sign(signing_input: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def create_access_token(
    user: PortalUser,
    *,
    expires_minutes: int | None = None,
    issued_at: int | None = None,
) -> str:
    """
    Cria token JWT Bearer com os dados e permissoes do usuario.
    """
    algorithm = _jwt_algorithm()
    if algorithm != "HS256":
        raise TokenError("Algoritmo JWT nao suportado")

    now = int(time.time()) if issued_at is None else issued_at
    expires_in = (expires_minutes or _jwt_expire_minutes()) * 60
    header = {"alg": algorithm, "typ": "JWT"}
    payload = {
        "sub": user.username,
        "iat": now,
        "exp": now + expires_in,
        "user": user.model_dump(),
    }

    encoded_header = _b64url_encode(_json_dumps(header))
    encoded_payload = _b64url_encode(_json_dumps(payload))
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = _sign(signing_input, _jwt_secret())
    return f"{signing_input}.{signature}"


def decode_access_token(token: str, *, now: int | None = None) -> dict[str, Any]:
    """
    Valida assinatura/expiracao e retorna o payload do token.
    """
    try:
        encoded_header, encoded_payload, signature = token.split(".", 2)
    except ValueError as exc:
        raise TokenError("Token invalido") from exc

    header = json.loads(_b64url_decode(encoded_header))
    if header.get("alg") != "HS256":
        raise TokenError("Algoritmo JWT invalido")

    signing_input = f"{encoded_header}.{encoded_payload}"
    expected_signature = _sign(signing_input, _jwt_secret())
    if not hmac.compare_digest(signature, expected_signature):
        raise TokenError("Assinatura JWT invalida")

    payload = json.loads(_b64url_decode(encoded_payload))
    current_time = int(time.time()) if now is None else now
    if int(payload.get("exp", 0)) <= current_time:
        raise TokenError("Token expirado")

    if not payload.get("user") or not payload.get("sub"):
        raise TokenError("Token sem usuario")

    return payload

