"""Parser HTML de status para modelos Brother."""

from html.parser import HTMLParser

from backend.app.modules.printers.monitoring.html_parsers.base import (
    HtmlStatusParseResult,
    HtmlStatusParser,
)
from backend.app.modules.printers.monitoring.state.rules import normalize_text


BROTHER_DCP_L1632W_STATUS_MESSAGES = (
    "Substituir toner",
    "Toner baixo",
    "Sem papel",
    "Atolamento",
    "Tampa aberta",
    "Dormindo",
    "Em espera",
    "Pronto",
    "Erro",
)


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._ignored_stack: list[str] = []
        self._chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript"}:
            self._ignored_stack.append(tag.lower())

    def handle_endtag(self, tag):
        if self._ignored_stack and self._ignored_stack[-1] == tag.lower():
            self._ignored_stack.pop()

    def handle_data(self, data):
        if self._ignored_stack:
            return
        text = " ".join(data.replace("\xa0", " ").split())
        if text:
            self._chunks.append(text)

    @property
    def chunks(self) -> list[str]:
        return list(self._chunks)


def extract_visible_text_chunks(html: str) -> list[str]:
    parser = VisibleTextParser()
    parser.feed(html or "")
    parser.close()
    return parser.chunks


class BrotherDcpL1632wStatusParser(HtmlStatusParser):
    parser_name = "brother_dcp_l1632w_status"
    supported_manufacturer = "Brother"
    supported_model = "DCP-L1632W"

    def parse(self, html: str) -> HtmlStatusParseResult:
        messages = self._extract_status_messages(html)
        if not messages:
            return self.error_result(
                "html_status_nao_encontrado",
                "Estado da maquina nao encontrado no HTML de status.",
            )
        return self.success_result(messages)

    def _extract_status_messages(self, html: str) -> list[str]:
        chunks = extract_visible_text_chunks(html)
        found: list[str] = []

        for chunk in chunks:
            normalized_chunk = normalize_text(chunk)
            for message in BROTHER_DCP_L1632W_STATUS_MESSAGES:
                normalized_message = normalize_text(message)
                if normalized_message == "erro" and self._has_negative_error_context(
                    normalized_chunk
                ):
                    continue
                if normalized_message in normalized_chunk and message not in found:
                    found.append(message)

        return found

    def _has_negative_error_context(self, normalized_text: str) -> bool:
        return any(
            context in normalized_text
            for context in (
                "sem erro",
                "nenhum erro",
                "sem erros",
                "nenhum erro detectado",
            )
        )

