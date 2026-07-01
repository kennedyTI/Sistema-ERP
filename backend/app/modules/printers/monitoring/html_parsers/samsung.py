"""Parser HTML de status para modelos Samsung."""

from backend.app.modules.printers.monitoring.html_parsers.base import (
    HtmlStatusParseResult,
    HtmlStatusParser,
    unique_messages,
)
from backend.app.modules.printers.monitoring.html_parsers.brother import (
    extract_visible_text_chunks,
)
from backend.app.modules.printers.monitoring.state.rules import normalize_text


class SamsungK4350StatusParser(HtmlStatusParser):
    parser_name = "samsung_k4350_status"
    supported_manufacturer = "Samsung"
    supported_model = "K-4350"
    supported_model_aliases = ("K4250LX", "K-4250LX", "K4350")

    def parse(self, html: str) -> HtmlStatusParseResult:
        messages = self._extract_status_messages(html)
        if not messages:
            return self.error_result(
                "html_status_nao_encontrado",
                "Estado ou alerta Samsung nao encontrado no HTML de status.",
            )
        return self.success_result(messages, estado_principal=messages[0])

    def _extract_status_messages(self, html: str) -> list[str]:
        chunks = extract_visible_text_chunks(html)
        found: list[str] = []

        for index, chunk in enumerate(chunks):
            normalized = normalize_text(chunk)
            if normalized.startswith("estado"):
                value = self._value_after_separator(chunk)
                if not value:
                    value = self._next_operational_value(chunks, index)
                if value:
                    found.append(value)
            if normalized.startswith("alerta"):
                value = self._value_after_separator(chunk)
                if not value:
                    value = self._next_operational_value(chunks, index)
                if value:
                    found.append(value)

        return unique_messages(found)

    def _value_after_separator(self, value: str) -> str | None:
        if ":" in value:
            return value.split(":", 1)[1].strip() or None
        return None

    def _next_operational_value(self, chunks: list[str], index: int) -> str | None:
        for candidate in chunks[index + 1 : index + 4]:
            normalized = normalize_text(candidate)
            if normalized in {"erro"} or "alerta" in normalized:
                return candidate
        return None
