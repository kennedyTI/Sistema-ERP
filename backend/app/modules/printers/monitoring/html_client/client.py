"""Cliente HTML seguro para fallback futuro de alertas."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from ipaddress import ip_address
from typing import Any
from urllib.parse import urljoin, urlsplit

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
UNSUPPORTED_AUTH_TYPES = ("cookie",)
BROTHER_FORM_AUTH_TYPES = ("form",)
LOGIN_CONTAINER_ID = "LogInOutBox"
PASSWORD_INPUT_ID = "LogBox"
VOID_HTML_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


@dataclass
class BrotherLoginForm:
    container_detected: bool = False
    form_detected: bool = False
    action: str | None = None
    method: str = "post"
    hidden_fields: dict[str, str] = field(default_factory=dict)
    password_input_detected: bool = False
    password_field_name: str | None = None
    csrf_detected: bool = False

    def safe_metadata(self) -> dict[str, Any]:
        return {
            "login_container_detected": self.container_detected,
            "login_form_detected": self.form_detected,
            "login_container_id": LOGIN_CONTAINER_ID,
            "password_input_detected": self.password_input_detected,
            "password_input_id": PASSWORD_INPUT_ID,
            "csrf_detected": self.csrf_detected,
            "hidden_fields_count": len(self.hidden_fields),
            "post_executado": False,
            "cookies_recebidos": False,
        }


class BrotherLoginFormParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.form = BrotherLoginForm()
        self._container_depth = 0
        self._form_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        normalized_tag = tag.lower()
        attributes = {key.lower(): value or "" for key, value in attrs}

        if self._container_depth > 0 and normalized_tag not in VOID_HTML_TAGS:
            self._container_depth += 1
        elif attributes.get("id") == LOGIN_CONTAINER_ID:
            self.form.container_detected = True
            self._container_depth = 1

        if self._container_depth <= 0:
            return

        if normalized_tag == "form" and self._form_depth == 0:
            self.form.form_detected = True
            self.form.action = attributes.get("action") or None
            self.form.method = (attributes.get("method") or "post").lower()
            self._form_depth = 1
            return

        if self._form_depth > 0 and normalized_tag not in VOID_HTML_TAGS:
            self._form_depth += 1

        if normalized_tag != "input" or self._form_depth <= 0:
            return

        input_id = attributes.get("id")
        input_name = attributes.get("name")
        input_type = (attributes.get("type") or "text").lower()
        field_name = input_name or input_id

        if input_type == "hidden" and field_name:
            self.form.hidden_fields[field_name] = attributes.get("value") or ""
            if _is_csrf_field(input_id) or _is_csrf_field(input_name):
                self.form.csrf_detected = True

        if input_id == PASSWORD_INPUT_ID:
            self.form.password_input_detected = True
            self.form.password_field_name = field_name or PASSWORD_INPUT_ID

    def handle_endtag(self, tag: str):
        normalized_tag = tag.lower()
        if self._form_depth > 0:
            self._form_depth -= 1
            if normalized_tag == "form":
                self._form_depth = 0
        if self._container_depth > 0:
            self._container_depth -= 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]):
        self.handle_starttag(tag, attrs)


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


def parse_brother_login_form(html: str | None) -> BrotherLoginForm:
    parser = BrotherLoginFormParser()
    parser.feed(html or "")
    return parser.form


def _is_csrf_field(value: str | None) -> bool:
    return (value or "").lower() == "csrftoken"


def _safe_login_metadata(**overrides) -> dict[str, Any]:
    metadata = BrotherLoginForm().safe_metadata()
    metadata.update(overrides)
    return metadata


def _port_from_url(parsed_url) -> int:
    if parsed_url.port:
        return parsed_url.port
    if parsed_url.scheme == "https":
        return 443
    return 80


def _resolve_brother_form_action(login_url: str, action: str | None) -> str:
    if not action:
        return login_url
    if any(char in action for char in ("\r", "\n", "\t", "\\")):
        raise HtmlClientError(
            "login_form_action_invalido",
            "Action do formulario de login contem caractere invalido.",
        )

    parsed_login = urlsplit(login_url)
    parsed_action = urlsplit(action)
    if parsed_action.scheme or parsed_action.netloc:
        if parsed_action.scheme not in ("http", "https"):
            raise HtmlClientError(
                "login_form_action_invalido",
                "Action absoluto do formulario usa protocolo invalido.",
            )
        if (
            parsed_action.hostname != parsed_login.hostname
            or _port_from_url(parsed_action) != _port_from_url(parsed_login)
        ):
            raise HtmlClientError(
                "login_form_action_host_invalido",
                "Action absoluto do formulario aponta para host externo.",
            )
        return action

    if action.startswith("//"):
        raise HtmlClientError(
            "login_form_action_host_invalido",
            "Action relativo do formulario aponta para host externo.",
        )
    return urljoin(login_url, action)


def _has_session_cookies(session, response=None) -> bool:
    cookies = getattr(session, "cookies", None)
    if cookies:
        return True
    response_cookies = getattr(response, "cookies", None)
    return bool(response_cookies)


def _failure_response(
    *,
    config: HtmlAccessConfig,
    code: str,
    detail: str,
    url: str | None = None,
    protocol: str | None = None,
    status_code: int | None = None,
    metadados: dict[str, Any] | None = None,
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
        metadados=metadados,
    )


def _successful_response(
    *,
    config: HtmlAccessConfig,
    response,
    url: str,
    protocol: str,
    metadados: dict[str, Any] | None = None,
) -> HtmlClientResponse:
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
        metadados=metadados,
    )


def _fetch_brother_form_page(
    ip_value: str,
    config: HtmlAccessConfig,
    *,
    page_type: str,
    session=None,
) -> HtmlClientResponse:
    try:
        target_path = validate_relative_html_path(
            path_for_page(config, page_type),
            field_name=f"caminho_{page_type}",
        )
        login_path = validate_relative_html_path(
            config.caminho_login or config.caminho_status,
            field_name="caminho_login",
        )
        if not target_path:
            raise HtmlClientError("caminho_html_nao_configurado", "Caminho HTML nao configurado.")
        if not login_path:
            raise HtmlClientError("caminho_login_nao_configurado", "Caminho de login HTML nao configurado.")
        validate_timeout(config.timeout_segundos)
        validate_port(config.porta)
        if not config.senha:
            raise HtmlClientError("credencial_html_incompleta", "Senha HTML nao informada.")
        protocols = protocol_sequence(config.protocolo_preferencial)
    except HtmlClientError as exc:
        return _failure_response(
            config=config,
            code=exc.code,
            detail=exc.detail,
            metadados=_safe_login_metadata(),
        )

    http_session = session or requests.Session()
    last_error: HtmlClientResponse | None = None

    for protocol in protocols:
        login_metadata = _safe_login_metadata()
        try:
            login_url = build_html_url(ip_value, protocol, login_path, port=config.porta)
            target_url = build_html_url(ip_value, protocol, target_path, port=config.porta)
        except (HtmlClientError, ValueError) as exc:
            return _failure_response(
                config=config,
                code=getattr(exc, "code", "ip_maquina_invalido"),
                detail=getattr(exc, "detail", "IP da maquina invalido."),
                protocol=protocol,
                metadados=login_metadata,
            )

        try:
            login_response = http_session.get(
                login_url,
                timeout=config.timeout_segundos,
                verify=config.validar_ssl,
            )
        except RequestException as exc:
            last_error = _failure_response(
                config=config,
                code="falha_requisicao_html",
                detail=exc.__class__.__name__,
                url=login_url,
                protocol=protocol,
                metadados=login_metadata,
            )
            continue

        if not (200 <= login_response.status_code < 400):
            return _successful_response(
                config=config,
                response=login_response,
                url=login_url,
                protocol=protocol,
                metadados=login_metadata,
            )

        form = parse_brother_login_form(login_response.text)
        login_metadata.update(form.safe_metadata())
        if form.container_detected:
            if not form.form_detected:
                return _failure_response(
                    config=config,
                    code="login_formulario_nao_detectado",
                    detail="Container de login encontrado sem formulario.",
                    url=login_url,
                    protocol=protocol,
                    metadados=login_metadata,
                )
            if not form.password_input_detected or not form.password_field_name:
                return _failure_response(
                    config=config,
                    code="login_password_input_nao_detectado",
                    detail="Input de senha do formulario Brother nao encontrado.",
                    url=login_url,
                    protocol=protocol,
                    metadados=login_metadata,
                )
            if form.method != "post":
                return _failure_response(
                    config=config,
                    code="login_form_method_invalido",
                    detail="Formulario Brother usa metodo diferente de POST.",
                    url=login_url,
                    protocol=protocol,
                    metadados=login_metadata,
                )
            try:
                action_url = _resolve_brother_form_action(login_url, form.action)
            except HtmlClientError as exc:
                return _failure_response(
                    config=config,
                    code=exc.code,
                    detail=exc.detail,
                    url=login_url,
                    protocol=protocol,
                    metadados=login_metadata,
                )

            payload = dict(form.hidden_fields)
            payload[form.password_field_name] = config.senha
            try:
                post_response = http_session.post(
                    action_url,
                    data=payload,
                    timeout=config.timeout_segundos,
                    verify=config.validar_ssl,
                    allow_redirects=True,
                )
            except RequestException as exc:
                login_metadata["post_executado"] = True
                return _failure_response(
                    config=config,
                    code="falha_login_formulario_html",
                    detail=exc.__class__.__name__,
                    url=login_url,
                    protocol=protocol,
                    metadados=login_metadata,
                )

            login_metadata["post_executado"] = True
            login_metadata["cookies_recebidos"] = _has_session_cookies(
                http_session,
                post_response,
            )
            if not (200 <= post_response.status_code < 400):
                return _failure_response(
                    config=config,
                    code="login_formulario_sem_sucesso",
                    detail=f"HTTP {post_response.status_code}",
                    url=login_url,
                    protocol=protocol,
                    status_code=post_response.status_code,
                    metadados=login_metadata,
                )

        try:
            target_response = http_session.get(
                target_url,
                timeout=config.timeout_segundos,
                verify=config.validar_ssl,
            )
        except RequestException as exc:
            last_error = _failure_response(
                config=config,
                code="falha_requisicao_html",
                detail=exc.__class__.__name__,
                url=target_url,
                protocol=protocol,
                metadados=login_metadata,
            )
            continue

        return _successful_response(
            config=config,
            response=target_response,
            url=target_url,
            protocol=protocol,
            metadados=login_metadata,
        )

    return last_error or _failure_response(
        config=config,
        code="falha_requisicao_html",
        detail="Falha ao acessar painel HTML.",
        metadados=_safe_login_metadata(),
    )


def fetch_html_page(
    ip_value: str,
    config: HtmlAccessConfig,
    *,
    page_type: str = "status",
    session=None,
) -> HtmlClientResponse:
    if config.tipo_autenticacao in BROTHER_FORM_AUTH_TYPES:
        return _fetch_brother_form_page(
            ip_value,
            config,
            page_type=page_type,
            session=session,
        )

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
