"""Configuracao ambiental da automacao de novo usuario Windows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from backend.app.core.config import BACKEND_DIR


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    return int(raw_value)


def _credential_path() -> Path:
    raw_path = os.getenv("AUTOMACAO_NOVO_USUARIO_CREDENCIAL_PATH")
    if not raw_path:
        portal_credentials_path = BACKEND_DIR / "Portal RH.url"
        if portal_credentials_path.exists():
            return portal_credentials_path.resolve()
        raw_path = str(BACKEND_DIR / "automacao_novo_usuario.local.ini")
    path = Path(raw_path)
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path.resolve()


@dataclass(frozen=True)
class NovoUsuarioAutomationSettings:
    dry_run: bool
    credential_path: Path
    email_provider: str
    pop_host: str
    pop_port: int
    pop_ssl: bool
    smtp_host: str
    smtp_port: int
    smtp_ssl: bool
    email_lookback_minutes: int
    pop_max_emails: int
    email_subject_prefix: str
    failure_email: str
    ad_domain: str
    ad_netbios: str
    ad_ou: str
    ad_office: str
    ad_company: str
    ad_groups: tuple[str, ...]
    powershell_timeout_seconds: int


def get_novo_usuario_settings() -> NovoUsuarioAutomationSettings:
    groups = tuple(
        group.strip()
        for group in os.getenv(
            "AUTOMACAO_NOVO_USUARIO_AD_GROUPS",
            "GR-USUARIOS-PADRAO,GR-INTERNET-PADRAO",
        ).split(",")
        if group.strip()
    )

    return NovoUsuarioAutomationSettings(
        dry_run=_env_bool("AUTOMACAO_NOVO_USUARIO_DRY_RUN", True),
        credential_path=_credential_path(),
        email_provider=os.getenv(
            "AUTOMACAO_NOVO_USUARIO_EMAIL_PROVIDER",
            "pop_smtp",
        ),
        pop_host=os.getenv("AUTOMACAO_NOVO_USUARIO_POP_HOST", "pop3.exemplo.local"),
        pop_port=_env_int("AUTOMACAO_NOVO_USUARIO_POP_PORT", 995),
        pop_ssl=_env_bool("AUTOMACAO_NOVO_USUARIO_POP_SSL", True),
        smtp_host=os.getenv("AUTOMACAO_NOVO_USUARIO_SMTP_HOST", "smtp.exemplo.local"),
        smtp_port=_env_int("AUTOMACAO_NOVO_USUARIO_SMTP_PORT", 465),
        smtp_ssl=_env_bool("AUTOMACAO_NOVO_USUARIO_SMTP_SSL", True),
        email_lookback_minutes=_env_int(
            "AUTOMACAO_NOVO_USUARIO_EMAIL_LOOKBACK_MINUTES",
            60,
        ),
        pop_max_emails=_env_int("AUTOMACAO_NOVO_USUARIO_POP_MAX_EMAILS", 30),
        email_subject_prefix=os.getenv(
            "AUTOMACAO_NOVO_USUARIO_EMAIL_SUBJECT_PREFIX",
            "ADMISSAO -",
        ),
        failure_email=os.getenv(
            "AUTOMACAO_NOVO_USUARIO_FAILURE_EMAIL",
            "suporte.ti@industria.local",
        ),
        ad_domain=os.getenv("AUTOMACAO_NOVO_USUARIO_AD_DOMAIN", "industria.local"),
        ad_netbios=os.getenv("AUTOMACAO_NOVO_USUARIO_AD_NETBIOS", "INDUSTRIA"),
        ad_ou=os.getenv(
            "AUTOMACAO_NOVO_USUARIO_AD_OU",
            "OU=Usuarios,OU=Corporativo,DC=industria,DC=local",
        ),
        ad_office=os.getenv(
            "AUTOMACAO_NOVO_USUARIO_AD_OFFICE",
            "Industria ERP",
        ),
        ad_company=os.getenv(
            "AUTOMACAO_NOVO_USUARIO_AD_COMPANY",
            "Industria",
        ),
        ad_groups=groups,
        powershell_timeout_seconds=_env_int(
            "AUTOMACAO_NOVO_USUARIO_POWERSHELL_TIMEOUT_SECONDS",
            120,
        ),
    )
