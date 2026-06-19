"""Cliente HTML seguro para fallback futuro de alertas."""

from ipaddress import ip_address
from urllib.parse import urlsplit

import requests
from requests import RequestException
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from backend.app.modules.printers.monitoring.html_client.exceptions import (
    HtmlClientError,
    UnsupportedAuthenticationError,
)
from backend.app.modules.printers.monitoring.html_client.models import (
    HtmlAccessConfig,
    HtmlClientResponse,
)


ALLOWED_PROTOCOLS = ("auto", "http", "https")
UNSUPPORTED_AUTH_TYPES = ("form", "cookie")


def validate_relative_html_path(path: str | None, *, field_name: str = "caminho") -> str | None:
    if path in (None, ""):
        return None

    if any(char in path for char in ("\r", "\n", "\t", "\\")):
        raise HtmlClientError("caminho_html_invalido", f"{field_name} contem caractere invalido.")

    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or path.startswith("//") or not path.startswith("/"):
        raise HtmlClientError(
            "caminho_html_invalido",
            f"{field_name} deve ser relativo e iniciar com /.",
        )

    return path


def validate_preferred_protocol(protocol: str) -> str:
    if protocol not in ALLOWED_PROTOCOLS:
        raise HtmlClientError(
            "protocolo_preferencial_invalido",
            "protocolo_preferencial deve ser auto, http ou https.",
        )
    return protocol


def validate_timeout(timeout_seconds: int) -> int:
    if timeout_seconds < 1 or timeout_seconds > 30:
        raise HtmlClientError(
            "timeout_html_invalido",
            "timeout_segundos deve ficar entre 1 e 30.",
        )
    return timeout_seconds


def validate_port(port: int | None) -> int:
    port = 80 if port is None else int(port)
    if port < 1 or port > 65535:
        raise HtmlClientError(
            "porta_html_invalida",
            "porta deve ficar entre 1 e 65535.",
        )
    return port


def protocol_sequence(preferred_protocol: str) -> tuple[str, ...]:
    protocol = validate_preferred_protocol(preferred_protocol)
    if protocol == "auto":
        return ("https", "http")
    return (protocol,)


def build_html_url(ip_value: str, protocol: str, path: str, *, port: int | None = 80) -> str:
    if protocol not in ("http", "https"):
        raise HtmlClientError("protocolo_html_invalido", "Protocolo HTML concreto invalido.")
    validated_path = validate_relative_html_path(path) or "/"
    validated_port = validate_port(port)
    address = ip_address(ip_value)
    host = f"[{address}]" if address.version == 6 else str(address)
    port_suffix = "" if validated_port == 80 or (protocol == "https" and validated_port == 443) else f":{validated_port}"
    return f"{protocol}://{host}{port_suffix}{validated_path}"


def path_for_page(config: HtmlAccessConfig, page_type: str) -> str | None:
    if page_type == "status":
        return config.caminho_status
    if page_type == "informacoes":
        return config.caminho_informacoes
    raise HtmlClientError("tipo_pagina_html_invalido", "Tipo de pagina HTML invalido.")


def build_auth(config: HtmlAccessConfig):
    if config.tipo_autenticacao in UNSUPPORTED_AUTH_TYPES:
        raise UnsupportedAuthenticationError()
    if config.tipo_autenticacao not in ("basic", "digest"):
        raise HtmlClientError(
            "tipo_autenticacao_invalido",
            "Tipo de autenticacao HTML invalido.",
        )
    if not config.senha:
        raise HtmlClientError("credencial_html_incompleta", "Senha HTML nao informada.")

    username = config.usuario or ""
    if config.tipo_autenticacao == "basic":
        return HTTPBasicAuth(username, config.senha)
    return HTTPDigestAuth(username, config.senha)


def _failure_response(
    *,
    config: HtmlAccessConfig,
    code: str,
    detail: str,
    url: str | None = None,
    protocol: str | None = None,
    status_code: int | None = None,
) -> HtmlClientResponse:
    return HtmlClientResponse(
        sucesso=False,
        status_code=status_code,
        url_sanitizada=url,
        conteudo_html=None,
        erro_codigo=code,
        erro_detalhe_sanitizado=detail,
        protocolo_usado=protocol,
        tipo_autenticacao=config.tipo_autenticacao,
    )


def fetch_html_page(
    ip_value: str,
    config: HtmlAccessConfig,
    *,
    page_type: str = "status",
    session=None,
) -> HtmlClientResponse:
    try:
        path = validate_relative_html_path(
            path_for_page(config, page_type),
            field_name=f"caminho_{page_type}",
        )
        if not path:
            raise HtmlClientError("caminho_html_nao_configurado", "Caminho HTML nao configurado.")
        validate_timeout(config.timeout_segundos)
        validate_port(config.porta)
        auth = build_auth(config)
        protocols = protocol_sequence(config.protocolo_preferencial)
    except HtmlClientError as exc:
        return _failure_response(config=config, code=exc.code, detail=exc.detail)

    http_session = session or requests.Session()
    last_error: HtmlClientResponse | None = None

    for protocol in protocols:
        try:
            url = build_html_url(ip_value, protocol, path, port=config.porta)
        except (HtmlClientError, ValueError) as exc:
            return _failure_response(
                config=config,
                code=getattr(exc, "code", "ip_maquina_invalido"),
                detail=getattr(exc, "detail", "IP da maquina invalido."),
                protocol=protocol,
            )
        try:
            response = http_session.get(
                url,
                auth=auth,
                timeout=config.timeout_segundos,
                verify=config.validar_ssl,
            )
        except RequestException as exc:
            last_error = _failure_response(
                config=config,
                code="falha_requisicao_html",
                detail=exc.__class__.__name__,
                url=url,
                protocol=protocol,
            )
            continue

        success = 200 <= response.status_code < 400
        return HtmlClientResponse(
            sucesso=success,
            status_code=response.status_code,
            url_sanitizada=url,
            conteudo_html=response.text if success else None,
            erro_codigo=None if success else "http_status_sem_sucesso",
            erro_detalhe_sanitizado=None if success else f"HTTP {response.status_code}",
            protocolo_usado=protocol,
            tipo_autenticacao=config.tipo_autenticacao,
        )

    return last_error or _failure_response(
        config=config,
        code="falha_requisicao_html",
        detail="Falha ao acessar painel HTML.",
    )
