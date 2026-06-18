"""Services internos das credenciais de coleta HTML."""

from sqlalchemy.orm import Session

from backend.app.modules.printers.monitoring.html_credentials.crypto import (
    decrypt_password,
    encrypt_password,
)
from backend.app.modules.printers.monitoring.html_credentials.models import (
    PrinterCollectionCredential,
)


def credential_metadata(credential: PrinterCollectionCredential | None) -> dict | None:
    if credential is None:
        return None
    return {
        "id": credential.id,
        "nome": credential.nome,
        "descricao": credential.descricao,
        "tipo_autenticacao": credential.tipo_autenticacao,
        "modelo_id": credential.modelo_id,
        "usuario": credential.usuario,
        "ativo": credential.ativo,
        "criado_em": credential.criado_em,
        "atualizado_em": credential.atualizado_em,
    }


def get_active_credential_for_model(
    db: Session,
    *,
    model_id: int,
) -> PrinterCollectionCredential | None:
    return (
        db.query(PrinterCollectionCredential)
        .filter(
            PrinterCollectionCredential.modelo_id == model_id,
            PrinterCollectionCredential.ativo.is_(True),
        )
        .one_or_none()
    )


def get_credential_metadata_for_model(db: Session, *, model_id: int) -> dict | None:
    return credential_metadata(get_active_credential_for_model(db, model_id=model_id))


def get_decrypted_credential_for_model(db: Session, *, model_id: int) -> dict | None:
    credential = get_active_credential_for_model(db, model_id=model_id)
    if credential is None:
        return None

    metadata = credential_metadata(credential) or {}
    metadata["senha"] = decrypt_password(credential.senha_criptografada)
    return metadata


def create_collection_credential(
    db: Session,
    *,
    nome: str,
    tipo_autenticacao: str,
    modelo_id: int,
    usuario: str,
    senha: str,
    descricao: str | None = None,
    ativo: bool = True,
) -> PrinterCollectionCredential:
    credential = PrinterCollectionCredential(
        nome=nome,
        descricao=descricao,
        tipo_autenticacao=tipo_autenticacao,
        modelo_id=modelo_id,
        usuario=usuario,
        senha_criptografada=encrypt_password(senha),
        ativo=ativo,
    )
    db.add(credential)
    db.flush()
    return credential

