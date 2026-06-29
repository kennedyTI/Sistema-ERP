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
    "Modo de espera.",
    "Ocorreu um erro.",
    "O toner Magenta está baixo.",
    "O toner Amarelo está baixo.",
    "Poderá ter ocorrido um erro.",
)


CANON_SECTION_STOP_TERMS = (
    "scanner",
    "detalhes do erro",
    "error details",
    "informacoes de erro",
    "error information",
    "informacao de erro",
    "informacoes de consumiveis",
    "consumables information",
    "informacao sobre papel",
    "paper information",
)

CANON_EMPTY_ERROR_TERMS = (
    "nenhum",
    "none",
    "sem erro",
    "sem informacoes",
    "status",
    "details",
    "detalhes",
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
        error_messages = self._extract_error_info_messages(chunks)
        if error_messages:
            return error_messages

        printer_state = self._extract_printer_state_messages(chunks)
        if printer_state:
            return printer_state

        return self._extract_known_status_messages(chunks)

    def _extract_error_info_messages(self, chunks: list[str]) -> list[str]:
        found: list[str] = []
        start_index = None

        for index, chunk in enumerate(chunks):
            normalized = normalize_text(chunk)
            if normalized.startswith("informacoes de erro") or normalized.startswith("error information"):
                start_index = index + 1
                break

        if start_index is None:
            return []

        index = start_index
        while index < len(chunks):
            chunk = chunks[index]
            normalized = normalize_text(chunk)
            if any(normalized.startswith(term) for term in CANON_SECTION_STOP_TERMS):
                break
            if not normalized or normalized in CANON_EMPTY_ERROR_TERMS:
                index += 1
                continue
            if (
                normalized.startswith("o toner ")
                and "baixo" not in normalized
                and index + 1 < len(chunks)
                and "baixo" in normalize_text(chunks[index + 1])
            ):
                found.append(f"{chunk} {chunks[index + 1]}")
                index += 2
                continue
            found.append(chunk)
            index += 1

        return unique_messages(found)

    def _extract_printer_state_messages(self, chunks: list[str]) -> list[str]:
        for index, chunk in enumerate(chunks):
            normalized = normalize_text(chunk)
            if not normalized.startswith("impressora") and not normalized.startswith("printer"):
                continue

            inline_state = self._state_after_printer_label(chunk)
            if inline_state:
                return unique_messages([inline_state])

            for next_chunk in chunks[index + 1 : index + 5]:
                normalized_next = normalize_text(next_chunk)
                if not normalized_next:
                    continue
                if normalized_next.startswith("scanner") or normalized_next.startswith("informacoes de erro"):
                    break
                if normalized_next in {"funcao", "estado", "printer", "impressora"}:
                    continue
                return unique_messages([next_chunk])

        return []

    def _state_after_printer_label(self, chunk: str) -> str | None:
        if ":" not in chunk:
            return None
        _, value = chunk.split(":", 1)
        cleaned = " ".join(value.split())
        normalized = normalize_text(cleaned)
        if normalized.startswith("impressora "):
            cleaned = " ".join(cleaned.split()[1:])
        return cleaned or None

    def _extract_known_status_messages(self, chunks: list[str]) -> list[str]:
        found: list[str] = []
        ignored_scanner_indexes: set[int] = set()

        for index, chunk in enumerate(chunks):
            if normalize_text(chunk).startswith("scanner"):
                ignored_scanner_indexes.update(range(index, min(index + 2, len(chunks))))

        for index, chunk in enumerate(chunks):
            if index in ignored_scanner_indexes:
                continue
            normalized_current = normalize_text(chunk)
            normalized_chunk = normalize_text(" ".join(chunks[index : index + 4]))
            for message in CANON_STATUS_MESSAGES:
                if "modo de espera" in normalize_text(message):
                    if "modo de espera" in normalized_current and self._is_printer_state_chunk(chunks, index):
                        found.append(message)
                    continue
                if normalize_text(message) in normalized_chunk:
                    found.append(message)

        return unique_messages(found)

    def _is_printer_state_chunk(self, chunks: list[str], index: int) -> bool:
        current_window = normalize_text(" ".join(chunks[max(index - 2, 0) : index + 2]))
        if "impressora" in current_window and "scanner" not in current_window:
            return True

        for previous_index in range(index - 1, max(index - 8, -1), -1):
            previous = normalize_text(chunks[previous_index])
            if any(previous.startswith(term) for term in CANON_SECTION_STOP_TERMS):
                return False
            if previous.startswith("impressora"):
                return True
        return False
