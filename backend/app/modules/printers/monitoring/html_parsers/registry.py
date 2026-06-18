"""Registry dos parsers HTML por modelo de impressora."""

from typing import Any

from backend.app.modules.printers.monitoring.html_client.models import HtmlClientResponse
from backend.app.modules.printers.monitoring.html_parsers.base import (
    HtmlStatusParseResult,
    HtmlStatusParser,
)
from backend.app.modules.printers.monitoring.html_parsers.brother import (
    BrotherDcpL1632wStatusParser,
)
from backend.app.modules.printers.monitoring.state.rules import normalize_text


PARSER_CLASSES: tuple[type[HtmlStatusParser], ...] = (
    BrotherDcpL1632wStatusParser,
)


def _model_value(model: Any, field_name: str) -> str | None:
    if isinstance(model, dict):
        value = model.get(field_name)
    else:
        value = getattr(model, field_name, None)
    return str(value) if value not in (None, "") else None


def _model_identity(model: Any) -> tuple[str | None, str | None]:
    return _model_value(model, "manufacturer"), _model_value(model, "name")


def _registry_key(manufacturer: str | None, model_name: str | None) -> tuple[str, str]:
    return normalize_text(manufacturer), normalize_text(model_name)


def _parser_key(parser: HtmlStatusParser) -> tuple[str, str]:
    return _registry_key(parser.supported_manufacturer, parser.supported_model)


def get_status_parser_for_model(model: Any) -> HtmlStatusParser | None:
    manufacturer, model_name = _model_identity(model)
    lookup_key = _registry_key(manufacturer, model_name)

    for parser_class in PARSER_CLASSES:
        parser = parser_class()
        if _parser_key(parser) == lookup_key:
            return parser
    return None


def _error_result_for_model(
    model: Any,
    *,
    code: str,
    detail: str,
    parser_name: str = "html_status_parser_registry",
) -> HtmlStatusParseResult:
    manufacturer, model_name = _model_identity(model)
    return HtmlStatusParseResult(
        sucesso=False,
        modelo_nome=model_name,
        fabricante=manufacturer,
        mensagens_brutas=[],
        mensagens_normalizadas=[],
        estado_principal=None,
        erro_codigo=code,
        erro_detalhe_sanitizado=detail,
        metadados={
            "parser": parser_name,
            "origem": "html_status",
        },
    )


def parse_status_html_for_model(model: Any, html: str) -> HtmlStatusParseResult:
    parser = get_status_parser_for_model(model)
    if parser is None:
        return _error_result_for_model(
            model,
            code="html_status_parser_nao_configurado",
            detail="Parser HTML de status nao configurado para este modelo.",
        )
    return parser.parse(html)


def parse_html_status_response(
    model: Any,
    response: HtmlClientResponse,
) -> HtmlStatusParseResult:
    if not response.sucesso or not response.conteudo_html:
        return _error_result_for_model(
            model,
            code="html_status_response_invalida",
            detail="Resposta HTML de status indisponivel para parser.",
        )
    return parse_status_html_for_model(model, response.conteudo_html)

