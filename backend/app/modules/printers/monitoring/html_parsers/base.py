"""Contratos internos dos parsers HTML de impressoras."""

from dataclasses import dataclass, field
from typing import Any

from backend.app.modules.printers.monitoring.state.rules import normalize_text


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
    supported_model_aliases: tuple[str, ...] = ()

    def parse(self, html: str) -> HtmlStatusParseResult:
        raise NotImplementedError

    def success_result(
        self,
        messages: list[str],
        *,
        estado_principal: str | None = None,
        metadados: dict[str, Any] | None = None,
    ) -> HtmlStatusParseResult:
        normalized_messages = [normalize_text(message) for message in messages]
        result_metadata = {
            "parser": self.parser_name,
            "origem": "html_status",
        }
        if metadados:
            result_metadata.update(metadados)
        return HtmlStatusParseResult(
            sucesso=True,
            modelo_nome=self.supported_model,
            fabricante=self.supported_manufacturer,
            mensagens_brutas=messages,
            mensagens_normalizadas=normalized_messages,
            estado_principal=estado_principal or choose_primary_status(messages),
            erro_codigo=None,
            erro_detalhe_sanitizado=None,
            metadados=result_metadata,
        )

    def error_result(
        self,
        code: str,
        detail: str,
        *,
        metadados: dict[str, Any] | None = None,
    ) -> HtmlStatusParseResult:
        result_metadata = {
            "parser": self.parser_name,
            "origem": "html_status",
        }
        if metadados:
            result_metadata.update(metadados)
        return HtmlStatusParseResult(
            sucesso=False,
            modelo_nome=self.supported_model,
            fabricante=self.supported_manufacturer,
            mensagens_brutas=[],
            mensagens_normalizadas=[],
            estado_principal=None,
            erro_codigo=code,
            erro_detalhe_sanitizado=detail,
            metadados=result_metadata,
        )


def unique_messages(messages: list[str]) -> list[str]:
    unique: list[str] = []
    normalized_seen: set[str] = set()
    for message in messages:
        cleaned = " ".join((message or "").split())
        normalized = normalize_text(cleaned)
        if not cleaned or normalized in normalized_seen:
            continue
        unique.append(cleaned)
        normalized_seen.add(normalized)
    return unique


def choose_primary_status(messages: list[str]) -> str | None:
    if not messages:
        return None

    priority_terms = (
        ("erro", "atolamento", "preso", "tampa aberta", "ocorreu um erro"),
        ("aviso", "baixo", "pouco toner", "subs.", "substituir", "trocar"),
        ("ok", "pronto", "ready", "espera", "sleep", "dormindo"),
    )

    best_message = messages[0]
    best_priority = len(priority_terms)
    for message in messages:
        normalized = normalize_text(message)
        for priority, terms in enumerate(priority_terms):
            if any(term in normalized for term in terms):
                if priority < best_priority:
                    best_message = message
                    best_priority = priority
                break
    return best_message
