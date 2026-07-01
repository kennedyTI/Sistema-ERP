"""Services internos das credenciais de coleta HTML."""

from sqlalchemy.orm import Session

from backend.app.modules.printers.machines.models import PrinterModel
from backend.app.modules.printers.monitoring.html_client.client import (
    validate_port,
    validate_preferred_protocol,
    validate_relative_html_path,
    validate_timeout,
)
from backend.app.modules.printers.monitoring.html_client.models import HtmlAccessConfig
from backend.app.modules.printers.monitoring.html_credentials.crypto import (
    decrypt_password,
    encrypt_password,
)
from backend.app.modules.printers.monitoring.html_credentials.models import (
    PrinterCollectionCredential,
)


def build_html_access_description(*, printer_model=None, caminho_status: str | None = None) -> str:
    model_label = "modelo nao informado"
    if printer_model is not None:
        manufacturer = getattr(printer_model, "manufacturer", None)
        name = getattr(printer_model, "name", None)
        model_label = " ".join(value for value in (manufacturer, name) if value) or str(printer_model)

    description = f"Coleta HTML autenticada para {model_label}"
    if caminho_status:
        description = f"{description} - status: {caminho_status}"
    return description


def _validated_path(path: str | None, *, field_name: str) -> str | None:
    return validate_relative_html_path(path, field_name=field_name)


def credential_metadata(credential: PrinterCollectionCredential | None) -> dict | None:
    if credential is None:
        return None
    return {
        "id": credential.id,
        "descricao": credential.descricao,
        "tipo_autenticacao": credential.tipo_autenticacao,
        "modelo_id": credential.modelo_id,
        "usuario": credential.usuario,
        "caminho_status": credential.caminho_status,
        "caminho_informacoes": credential.caminho_informacoes,
        "caminho_login": credential.caminho_login,
        "porta": credential.porta,
        "timeout_segundos": credential.timeout_segundos,
        "protocolo_preferencial": credential.protocolo_preferencial,
        "validar_ssl": credential.validar_ssl,
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


def get_active_html_access_for_model(db: Session, *, model_id: int) -> dict | None:
    return get_credential_metadata_for_model(db, model_id=model_id)


def get_decrypted_html_access_for_model(db: Session, *, model_id: int) -> HtmlAccessConfig | None:
    credential = get_active_credential_for_model(db, model_id=model_id)
    if credential is None:
        return None

    return HtmlAccessConfig(
        modelo_id=credential.modelo_id,
        tipo_autenticacao=credential.tipo_autenticacao,
        usuario=credential.usuario,
        senha=decrypt_password(credential.senha_criptografada),
        caminho_status=credential.caminho_status,
        caminho_informacoes=credential.caminho_informacoes,
        caminho_login=credential.caminho_login,
        porta=credential.porta,
        timeout_segundos=credential.timeout_segundos,
        protocolo_preferencial=credential.protocolo_preferencial,
        validar_ssl=credential.validar_ssl,
    )


def create_collection_credential(
    db: Session,
    *,
    tipo_autenticacao: str,
    modelo_id: int,
    senha: str,
    usuario: str | None = None,
    caminho_status: str | None = None,
    caminho_informacoes: str | None = None,
    caminho_login: str | None = None,
    porta: int = 80,
    timeout_segundos: int = 5,
    protocolo_preferencial: str = "auto",
    validar_ssl: bool = False,
    ativo: bool = True,
) -> PrinterCollectionCredential:
    caminho_status = _validated_path(caminho_status, field_name="caminho_status")
    caminho_informacoes = _validated_path(
        caminho_informacoes,
        field_name="caminho_informacoes",
    )
    caminho_login = _validated_path(caminho_login, field_name="caminho_login")
    validate_port(porta)
    validate_timeout(timeout_segundos)
    validate_preferred_protocol(protocolo_preferencial)
    printer_model = db.get(PrinterModel, modelo_id)

    credential = PrinterCollectionCredential(
        descricao=build_html_access_description(
            printer_model=printer_model,
            caminho_status=caminho_status,
        ),
        tipo_autenticacao=tipo_autenticacao,
        modelo_id=modelo_id,
        usuario=usuario,
        senha_criptografada=encrypt_password(senha),
        caminho_status=caminho_status,
        caminho_informacoes=caminho_informacoes,
        caminho_login=caminho_login,
        porta=porta,
        timeout_segundos=timeout_segundos,
        protocolo_preferencial=protocolo_preferencial,
        validar_ssl=validar_ssl,
        ativo=ativo,
    )
    db.add(credential)
    db.flush()
    return credential
