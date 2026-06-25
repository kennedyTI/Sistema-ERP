"""Parser HTML de status para modelos Canon."""

from backend.app.modules.printers.monitoring.html_parsers.base import (
    HtmlStatusParseResult,
    HtmlStatusParser,
    unique_messages,
)
from backend.app.modules.printers.monitoring.html_parsers.brother import (
    extract_visible_text_chunks,
)
from backend.app.modules.printers.monitoring.state.rules import normalize_text


CANON_STATUS_MESSAGES = (
    "Ocorreu um erro.",
    "O toner Magenta está baixo.",
    "O toner Amarelo está baixo.",
    "Poderá ter ocorrido um erro.",
)


class CanonIrC3326iStatusParser(HtmlStatusParser):
    parser_name = "canon_ir_c3326i_status"
    supported_manufacturer = "Canon"
    supported_model = "IR-C3326I"

    def parse(self, html: str) -> HtmlStatusParseResult:
        messages = self._extract_status_messages(html)
        if not messages:
            return self.error_result(
                "html_status_nao_encontrado",
                "Estado da impressora nao encontrado no HTML de status.",
            )
        return self.success_result(messages)

    def _extract_status_messages(self, html: str) -> list[str]:
        chunks = extract_visible_text_chunks(html)
        found: list[str] = []
        ignored_scanner_indexes: set[int] = set()

        for index, chunk in enumerate(chunks):
            if normalize_text(chunk).startswith("scanner"):
                ignored_scanner_indexes.update(range(index, min(index + 2, len(chunks))))

        for index, chunk in enumerate(chunks):
            if index in ignored_scanner_indexes:
                continue
            normalized_chunk = normalize_text(" ".join(chunks[index : index + 4]))
            for message in CANON_STATUS_MESSAGES:
                if normalize_text(message) in normalized_chunk:
                    found.append(message)

        return unique_messages(found)
