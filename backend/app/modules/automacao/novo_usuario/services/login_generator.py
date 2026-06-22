"""Geracao de login Windows a partir do nome completo."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


PARTICLES = {"de", "da", "do", "das", "dos", "e"}


@dataclass(frozen=True)
class LoginOptions:
    primary: str
    secondary: str | None
    first_name: str
    primary_surname: str
    secondary_surname: str | None


def normalize_login_part(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    ascii_value = ascii_value.lower()
    ascii_value = re.sub(r"[^a-z0-9]+", "", ascii_value)
    return ascii_value


def _name_tokens(full_name: str) -> list[str]:
    return [
        token.strip()
        for token in re.split(r"\s+", full_name.strip())
        if token.strip()
    ]


def _login_tokens(full_name: str) -> list[str]:
    tokens = [normalize_login_part(token) for token in _name_tokens(full_name)]
    return [
        token
        for token in tokens
        if token and token not in PARTICLES
    ]


def generate_login_options(full_name: str) -> LoginOptions:
    login_tokens = _login_tokens(full_name)
    if len(login_tokens) < 2:
        raise ValueError("Nome completo deve possuir primeiro nome e sobrenome.")

    first_name = login_tokens[0]
    primary_surname = login_tokens[-1]
    secondary_surname = login_tokens[-2] if len(login_tokens) >= 3 else None

    return LoginOptions(
        primary=f"{first_name}.{primary_surname}",
        secondary=(
            f"{first_name}.{secondary_surname}"
            if secondary_surname and secondary_surname != primary_surname
            else None
        ),
        first_name=first_name,
        primary_surname=primary_surname,
        secondary_surname=secondary_surname,
    )


def get_ad_name_parts(full_name: str) -> tuple[str, str]:
    original_tokens = _name_tokens(full_name)
    if len(original_tokens) < 2:
        raise ValueError("Nome completo deve possuir primeiro nome e sobrenome.")

    first_name = original_tokens[0]
    surnames = [
        token
        for token in original_tokens[1:]
        if normalize_login_part(token) not in PARTICLES
    ]
    if not surnames:
        raise ValueError("Nome completo deve possuir sobrenome valido.")
    return first_name, surnames[-1]
