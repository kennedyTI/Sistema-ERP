"""
Traducao simples de logs persistidos.

Nesta base limpa, os logs mantidos sao genericos e ligados ao ciclo de
autenticacao/acesso.
"""

from __future__ import annotations

LOG_TYPE_TRANSLATIONS = {
    "login_success": "Login realizado",
    "login_failed": "Falha de login",
    "logout": "Logout",
    "access_denied": "Acesso negado",
}

FIELD_TRANSLATIONS = {
    "usuario": "usuario",
    "sucesso": "sucesso",
    "path": "rota",
    "permission": "permissao",
}

VALUE_TRANSLATIONS = {
    "true": "sim",
    "false": "nao",
    "none": "nao informado",
    "null": "nao informado",
}


def _translate_key_value_text(value: str) -> str:
    segments = []

    for segment in value.split(";"):
        current = segment.strip()
        if not current:
            continue

        if "=" not in current:
            segments.append(current)
            continue

        key, raw_item_value = current.split("=", 1)
        key = key.strip()
        item_value = raw_item_value.strip()
        segments.append(
            f"{FIELD_TRANSLATIONS.get(key, key)}={VALUE_TRANSLATIONS.get(item_value.lower(), item_value)}"
        )

    return "; ".join(segments)


def translate_log_type(value: str | None) -> str | None:
    if value is None:
        return None
    return LOG_TYPE_TRANSLATIONS.get(value, str(value))


def translate_log_text(value: str | None) -> str | None:
    if value is None:
        return None

    text = str(value)
    if "=" in text:
        return _translate_key_value_text(text)
    return text


def translate_log_for_persistence(log) -> None:
    log.tipo = translate_log_type(log.tipo)
    log.message = translate_log_text(log.message)
    log.valor_anterior = translate_log_text(log.valor_anterior)
    log.valor_novo = translate_log_text(log.valor_novo)
