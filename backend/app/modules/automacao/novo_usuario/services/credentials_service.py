"""Leitura segura das credenciais locais da automacao."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.app.modules.automacao.novo_usuario.config import (
    NovoUsuarioAutomationSettings,
)


EMAIL_SECTION = "automacao_novo_usuario_email"
WINDOWS_SECTION = "automacao_novo_usuario_windows"


class CredentialConfigurationError(RuntimeError):
    """Erro de configuracao do arquivo local de credenciais."""


@dataclass(frozen=True)
class NovoUsuarioCredentials:
    email: str
    email_password: str = field(repr=False)
    temporary_password: str = field(repr=False)

    @property
    def temporary_password_masked(self) -> str:
        return mask_secret(self.temporary_password)


def mask_secret(secret: str | None) -> str:
    if not secret:
        return ""
    return "*" * len(secret)


def _read_known_sections(path: Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {
        EMAIL_SECTION: {},
        WINDOWS_SECTION: {},
    }
    current_section: str | None = None
    expected_keys = {
        EMAIL_SECTION: {"EMAIL", "SENHA"},
        WINDOWS_SECTION: {"SENHA_TEMPORARIA"},
    }

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section_name = line[1:-1].strip()
            current_section = section_name if section_name in sections else None
            continue
        if current_section is None or "=" not in line:
            continue

        key, value = line.split("=", 1)
        normalized_key = key.strip().upper()
        if normalized_key in expected_keys[current_section]:
            sections[current_section][normalized_key] = value.strip()

    return sections


def load_credentials_from_file(path: Path) -> NovoUsuarioCredentials:
    if not path.exists():
        raise CredentialConfigurationError(
            f"Arquivo de credenciais nao encontrado: {path}"
        )

    sections = _read_known_sections(path)

    missing_sections = [
        section
        for section in (EMAIL_SECTION, WINDOWS_SECTION)
        if not sections.get(section)
    ]
    if missing_sections:
        raise CredentialConfigurationError(
            "Secoes ausentes no arquivo de credenciais: "
            + ", ".join(missing_sections)
        )

    email = sections[EMAIL_SECTION].get("EMAIL", "").strip()
    email_password = sections[EMAIL_SECTION].get("SENHA", "")
    temporary_password = sections[WINDOWS_SECTION].get("SENHA_TEMPORARIA", "")

    missing_fields = []
    if not email:
        missing_fields.append(f"{EMAIL_SECTION}.EMAIL")
    if not email_password:
        missing_fields.append(f"{EMAIL_SECTION}.SENHA")
    if not temporary_password:
        missing_fields.append(f"{WINDOWS_SECTION}.SENHA_TEMPORARIA")

    if missing_fields:
        raise CredentialConfigurationError(
            "Campos obrigatorios ausentes no arquivo de credenciais: "
            + ", ".join(missing_fields)
        )

    return NovoUsuarioCredentials(
        email=email,
        email_password=email_password,
        temporary_password=temporary_password,
    )


def load_credentials(
    settings: NovoUsuarioAutomationSettings,
) -> NovoUsuarioCredentials:
    return load_credentials_from_file(settings.credential_path)
