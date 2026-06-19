"""Parser HTML de status para modelos Brother."""

from html.parser import HTMLParser

from backend.app.modules.printers.monitoring.html_parsers.base import (
    HtmlStatusParseResult,
    HtmlStatusParser,
    unique_messages,
)
from backend.app.modules.printers.monitoring.state.rules import normalize_text


BROTHER_DCP_L1632W_STATUS_MESSAGES = (
    "Subs. o toner",
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

BROTHER_DCP_L2540DW_STATUS_MESSAGES = (
    "Há pouco toner",
    "Trocar Toner",
    "Papel Preso",
    "Trocar Cilindro",
    "Ready",
    "Sleep",
    "Deep Sleep",
    "Em espera",
    "Pronto",
    "Dormindo",
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


def _find_message_after_label(
    chunks: list[str],
    *,
    labels: tuple[str, ...],
    known_messages: tuple[str, ...],
) -> list[str]:
    normalized_labels = tuple(normalize_text(label) for label in labels)
    known_by_normalized = {
        normalize_text(message): message
        for message in known_messages
    }
    found: list[str] = []

    for index, chunk in enumerate(chunks):
        normalized_chunk = normalize_text(chunk)
        if not any(label in normalized_chunk for label in normalized_labels):
            continue

        for candidate_index in range(index + 1, min(index + 9, len(chunks))):
            candidate_window = " ".join(chunks[candidate_index : candidate_index + 4])
            normalized_candidate = normalize_text(candidate_window)
            for normalized_message, message in known_by_normalized.items():
                if normalized_message in normalized_candidate:
                    found.append(message)
                    break
            if found:
                break

    return unique_messages(found)


def _find_known_messages(chunks: list[str], known_messages: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for index, chunk in enumerate(chunks):
        normalized_chunk = normalize_text(" ".join(chunks[index : index + 4]))
        for message in known_messages:
            normalized_message = normalize_text(message)
            if normalized_message == "erro" and any(
                context in normalized_chunk
                for context in (
                    "sem erro",
                    "nenhum erro",
                    "sem erros",
                    "nenhum erro detectado",
                )
            ):
                continue
            if normalized_message in normalized_chunk:
                found.append(message)
    return unique_messages(found)


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
        focused = _find_message_after_label(
            chunks,
            labels=("Estado do dispositivo", "Device Status", "Estado"),
            known_messages=BROTHER_DCP_L1632W_STATUS_MESSAGES,
        )
        if focused:
            return focused
        return _find_known_messages(chunks, BROTHER_DCP_L1632W_STATUS_MESSAGES)


class BrotherDcpL2540dwStatusParser(HtmlStatusParser):
    parser_name = "brother_dcp_l2540dw_status"
    supported_manufacturer = "Brother"
    supported_model = "DCP-L2540DW"

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
        focused = _find_message_after_label(
            chunks,
            labels=("Device Status", "Estado do dispositivo", "Status"),
            known_messages=BROTHER_DCP_L2540DW_STATUS_MESSAGES,
        )
        if focused:
            return focused
        return _find_known_messages(chunks, BROTHER_DCP_L2540DW_STATUS_MESSAGES)
