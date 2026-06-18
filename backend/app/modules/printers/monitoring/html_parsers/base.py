"""Contratos internos dos parsers HTML de impressoras."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HtmlStatusParseResult:
    sucesso: bool
    modelo_nome: str | None
    fabricante: str | None
    mensagens_brutas: list[str]
    mensagens_normalizadas: list[str]
    estado_principal: str | None
    erro_codigo: str | None
    erro_detalhe_sanitizado: str | None
    metadados: dict[str, Any] = field(default_factory=dict)


class HtmlStatusParser:
    parser_name = "html_status_parser"
    supported_manufacturer = ""
    supported_model = ""

    def parse(self, html: str) -> HtmlStatusParseResult:
        raise NotImplementedError

    def success_result(self, messages: list[str]) -> HtmlStatusParseResult:
        from backend.app.modules.printers.monitoring.state.rules import normalize_text

        normalized_messages = [normalize_text(message) for message in messages]
        return HtmlStatusParseResult(
            sucesso=True,
            modelo_nome=self.supported_model,
            fabricante=self.supported_manufacturer,
            mensagens_brutas=messages,
            mensagens_normalizadas=normalized_messages,
            estado_principal=messages[0] if messages else None,
            erro_codigo=None,
            erro_detalhe_sanitizado=None,
            metadados={
                "parser": self.parser_name,
                "origem": "html_status",
            },
        )

    def error_result(self, code: str, detail: str) -> HtmlStatusParseResult:
        return HtmlStatusParseResult(
            sucesso=False,
            modelo_nome=self.supported_model,
            fabricante=self.supported_manufacturer,
            mensagens_brutas=[],
            mensagens_normalizadas=[],
            estado_principal=None,
            erro_codigo=code,
            erro_detalhe_sanitizado=detail,
            metadados={
                "parser": self.parser_name,
                "origem": "html_status",
            },
        )

