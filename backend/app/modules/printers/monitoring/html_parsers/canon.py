"""Parser HTML de status para modelos Canon."""

import html as html_module
import json
import re

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

CANON_DYNAMIC_ERROR_TABLE_PATTERN = re.compile(
    r"var\s+errCodeTbl\s*=\s*new\s+Array\s*\((?P<values>.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
CANON_DYNAMIC_ERROR_ENTRY_PATTERN = re.compile(
    r"new\s+art_array_pri\s*\(\s*(?P<code>0x[0-9a-f]+)\s*,\s*"
    r'"(?P<message>(?:\\.|[^"])*)"',
    re.IGNORECASE | re.DOTALL,
)
CANON_DYNAMIC_PRINTER_STATUS_PATTERN = re.compile(
    r"var\s+prt_status\s*=\s*[\"'](?P<value>(?:0x)?[0-9a-f]+)[\"']",
    re.IGNORECASE,
)
CANON_DYNAMIC_PRINTER_TABLE_PATTERN = re.compile(
    r"var\s+prt_str_array\s*=\s*new\s+Array\s*\((?P<entries>.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
CANON_DYNAMIC_PRINTER_ENTRY_PATTERN = re.compile(
    r"new\s+stamsgarray\s*\(\s*(?P<code>0x[0-9a-f]+|\d+)\s*,\s*"
    r'"(?P<message>(?:\\.|[^"])*)"',
    re.IGNORECASE | re.DOTALL,
)
CANON_DYNAMIC_STATUS_TRANSLATIONS = {
    "a service call error occurred.": "Ocorreu um erro de serviço.",
    "a maintenance error occurred.": "Ocorreu um erro de manutenção.",
    "an error occurred.": "Ocorreu um erro.",
    "warming up...": "Aquecendo.",
    "sleep mode.": "Modo de espera.",
    "printing...": "Imprimindo.",
    "ready to print.": "Pronta para imprimir.",
}
CANON_TONER_COLOR_NAMES = {
    "ciano": "cyan",
    "cyan": "cyan",
    "magenta": "magenta",
    "amarelo": "yellow",
    "yellow": "yellow",
    "preto": "black",
    "black": "black",
}
CANON_TONER_SECTION_TERMS = {"toner restante", "remaining toner"}
CANON_TONER_SECTION_STOP_TERMS = {
    "painel de mensagem",
    "message board",
    "programacoes basicas",
    "basic settings",
}
CANON_TONER_SCRIPT_PATTERN = re.compile(
    r"var\s+tonerVolInfo\s*=\s*(?P<payload>\{.*?\})\s*;",
    re.IGNORECASE | re.DOTALL,
)
CANON_TONER_SCRIPT_COLORS = {
    "tonerCVol": "cyan",
    "tonerMVol": "magenta",
    "tonerYVol": "yellow",
    "tonerKVol": "black",
}


def parse_canon_ir_c3326i_toner_levels(html: str) -> list[dict[str, object]]:
    """Extrai somente percentuais de toner da secao de consumiveis Canon."""
    chunks = extract_visible_text_chunks(html or "")
    section_index = next(
        (
            index
            for index, chunk in enumerate(chunks)
            if normalize_text(chunk) in CANON_TONER_SECTION_TERMS
        ),
        None,
    )
    items: list[dict[str, object]] = []
    if section_index is not None:
        for index in range(section_index + 1, min(len(chunks), section_index + 32)):
            normalized = normalize_text(chunks[index]).strip(" :")
            if normalized in CANON_TONER_SECTION_STOP_TERMS:
                break
            color = CANON_TONER_COLOR_NAMES.get(normalized)
            if color is None:
                continue
            percentage = next(
                (
                    int(match.group(1))
                    for candidate in chunks[index + 1 : index + 4]
                    if (match := re.search(r"\b(\d{1,3})(?:[.,]\d+)?\s*%", candidate))
                    and 0 <= int(match.group(1)) <= 100
                ),
                None,
            )
            if percentage is not None:
                items.append({"cor": color, "percentual": percentage})
    if items:
        return items

    script_match = CANON_TONER_SCRIPT_PATTERN.search(html or "")
    if script_match is None:
        return []
    try:
        payload = json.loads(script_match.group("payload"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []

    for key, color in CANON_TONER_SCRIPT_COLORS.items():
        raw_value = payload.get(key)
        if isinstance(raw_value, bool):
            continue
        try:
            percentage = int(str(raw_value).strip())
        except (TypeError, ValueError):
            continue
        if 0 <= percentage <= 100:
            items.append({"cor": color, "percentual": percentage})
    return items


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

        has_dynamic_errors, dynamic_error_messages = self._extract_dynamic_error_messages(html)
        if has_dynamic_errors:
            return dynamic_error_messages or ["Ocorreu um erro."]

        printer_state = self._extract_printer_state_messages(chunks)
        if printer_state:
            return printer_state

        dynamic_printer_state = self._extract_dynamic_printer_state(html)
        if dynamic_printer_state:
            return dynamic_printer_state

        return self._extract_known_status_messages(chunks)

    def _extract_dynamic_error_messages(self, html: str) -> tuple[bool, list[str]]:
        table_match = CANON_DYNAMIC_ERROR_TABLE_PATTERN.search(html)
        if table_match is None:
            return False, []

        error_codes = [
            int(value, 16)
            for value in re.findall(
                r"0x[0-9a-f]+",
                table_match.group("values"),
                re.IGNORECASE,
            )
        ]
        if not error_codes:
            return False, []

        messages_by_code = {
            int(match.group("code"), 16): self._clean_dynamic_message(
                match.group("message")
            )
            for match in CANON_DYNAMIC_ERROR_ENTRY_PATTERN.finditer(html)
        }
        messages = [
            messages_by_code[code]
            for code in error_codes
            if messages_by_code.get(code)
        ]
        return True, unique_messages(messages)

    def _extract_dynamic_printer_state(self, html: str) -> list[str]:
        status_match = CANON_DYNAMIC_PRINTER_STATUS_PATTERN.search(html)
        table_match = CANON_DYNAMIC_PRINTER_TABLE_PATTERN.search(html)
        if status_match is None or table_match is None:
            return []

        status_value = self._parse_dynamic_number(status_match.group("value"))
        entries = [
            (
                self._parse_dynamic_number(match.group("code")),
                self._clean_dynamic_message(match.group("message")),
            )
            for match in CANON_DYNAMIC_PRINTER_ENTRY_PATTERN.finditer(
                table_match.group("entries")
            )
        ]
        if not entries:
            return []

        # A interface Canon testa igualdade e depois o primeiro bit aplicavel.
        selected_message = next(
            (message for code, message in entries if status_value == code),
            None,
        )
        if selected_message is None:
            selected_message = next(
                (message for code, message in entries if status_value & code),
                None,
            )
        if not selected_message:
            selected_message = entries[0][1]
        return unique_messages([self._translate_dynamic_status(selected_message)])

    def _clean_dynamic_message(self, value: str) -> str:
        cleaned = value.replace(r'\"', '"').replace(r"\/", "/")
        cleaned = cleaned.replace(r"\n", " ").replace(r"\r", " ").replace(r"\t", " ")
        cleaned = html_module.unescape(cleaned)
        cleaned = re.sub(r"\bxxx\s*", "", cleaned, flags=re.IGNORECASE)
        return " ".join(cleaned.split()).strip()

    def _translate_dynamic_status(self, message: str) -> str:
        return CANON_DYNAMIC_STATUS_TRANSLATIONS.get(
            normalize_text(message),
            message,
        )

    def _parse_dynamic_number(self, value: str) -> int:
        return int(value, 16) if value.casefold().startswith("0x") else int(value, 10)

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
