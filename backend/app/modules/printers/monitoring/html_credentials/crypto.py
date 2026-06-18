"""Criptografia das credenciais de coleta HTML."""

import os

from cryptography.fernet import Fernet, InvalidToken


ENV_SECRET_KEY = "PRINTER_CREDENTIALS_SECRET_KEY"


class CredentialCryptoError(RuntimeError):
    """Erro controlado para operacoes sensiveis de credenciais."""


def _load_secret_key(secret_key: str | None = None) -> bytes:
    value = secret_key if secret_key is not None else os.getenv(ENV_SECRET_KEY, "")
    if not value or not value.strip():
        raise CredentialCryptoError(
            "Chave de criptografia das credenciais nao configurada."
        )
    return value.strip().encode("utf-8")


def _fernet(secret_key: str | None = None) -> Fernet:
    try:
        return Fernet(_load_secret_key(secret_key))
    except ValueError as exc:
        raise CredentialCryptoError(
            "Chave de criptografia das credenciais invalida."
        ) from exc


def encrypt_password(plain_password: str, *, secret_key: str | None = None) -> str:
    if plain_password is None or plain_password == "":
        raise CredentialCryptoError("Senha da credencial nao informada.")
    return _fernet(secret_key).encrypt(plain_password.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted_password: str, *, secret_key: str | None = None) -> str:
    if not encrypted_password:
        raise CredentialCryptoError("Senha criptografada nao informada.")
    try:
        return _fernet(secret_key).decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise CredentialCryptoError("Senha criptografada invalida.") from exc

