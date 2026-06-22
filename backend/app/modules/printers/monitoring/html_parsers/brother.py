"""Parser HTML de status para modelos Brother."""

import re
from dataclasses import dataclass, field
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
TONER_LABELS = {"BK", "C", "M", "Y"}


@dataclass
class HtmlDefinitionBlock:
    tag: str
    chunks: list[str] = field(default_factory=list)
    moni_chunks: list[str] = field(default_factory=list)
    toner_labels: list[str] = field(default_factory=list)
    has_toner_bar: bool = False

    @property
    def text(self) -> str:
        return " ".join(self.chunks)

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


class DefinitionItemsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[HtmlDefinitionBlock] = []
        self._current: HtmlDefinitionBlock | None = None
        self._ignored_stack: list[str] = []
        self._element_stack: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag, attrs):
        normalized_tag = tag.lower()
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        self._element_stack.append((normalized_tag, attrs_dict))
        if normalized_tag in {"script", "style", "noscript"}:
            self._ignored_stack.append(normalized_tag)
        if normalized_tag in {"h3", "dt", "dd"}:
            self._current = HtmlDefinitionBlock(tag=normalized_tag)
        if (
            self._current
            and self._current.tag == "dd"
            and normalized_tag == "img"
            and "tonerremain" in attrs_dict.get("class", "")
        ):
            self._current.has_toner_bar = True

    def handle_endtag(self, tag):
        normalized_tag = tag.lower()
        if self._current and self._current.tag == normalized_tag:
            self.blocks.append(self._current)
            self._current = None
        if self._ignored_stack and self._ignored_stack[-1] == normalized_tag:
            self._ignored_stack.pop()
        for index in range(len(self._element_stack) - 1, -1, -1):
            if self._element_stack[index][0] == normalized_tag:
                del self._element_stack[index:]
                break

    def handle_data(self, data):
        if self._ignored_stack or not self._current:
            return
        text = " ".join(data.replace("\xa0", " ").split())
        if not text:
            return
        self._current.chunks.append(text)
        if self._inside_moni_status():
            self._current.moni_chunks.append(text)
        if self._inside_tag("th") and text.strip().upper() in TONER_LABELS:
            self._current.toner_labels.append(text.strip().upper())

    def _inside_tag(self, tag: str) -> bool:
        return any(stacked_tag == tag for stacked_tag, _attrs in self._element_stack)

    def _inside_moni_status(self) -> bool:
        has_moni_data = any(
            attrs.get("id") == "moni_data" for _tag, attrs in self._element_stack
        )
        has_moni_class = any(
            "moni" in attrs.get("class", "").split()
            for _tag, attrs in self._element_stack
        )
        return has_moni_data and has_moni_class


def parse_definition_blocks(html: str) -> list[HtmlDefinitionBlock]:
    parser = DefinitionItemsParser()
    parser.feed(html or "")
    parser.close()
    return parser.blocks


def definition_pairs(html: str) -> list[tuple[str, HtmlDefinitionBlock]]:
    blocks = parse_definition_blocks(html)
    pairs: list[tuple[str, HtmlDefinitionBlock]] = []
    for index, block in enumerate(blocks):
        if block.tag != "dt":
            continue
        next_block = blocks[index + 1] if index + 1 < len(blocks) else None
        if next_block and next_block.tag == "dd":
            pairs.append((block.text, next_block))
    return pairs


def definition_sections(html: str) -> list[tuple[str, str, str]]:
    blocks = parse_definition_blocks(html)
    section = ""
    rows: list[tuple[str, str, str]] = []
    for index, block in enumerate(blocks):
        if block.tag == "h3":
            section = block.text
            continue
        if block.tag != "dt":
            continue
        next_block = blocks[index + 1] if index + 1 < len(blocks) else None
        if next_block and next_block.tag == "dd":
            rows.append((section, block.text, next_block.text))
    return rows


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


def _extract_first_int(value: str) -> int | None:
    match = re.search(r"\d+", value.replace(".", "").replace(",", ""))
    return int(match.group(0)) if match else None


def _extract_percent(value: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*%", value)
    if not match:
        return None
    percent = int(match.group(1))
    return percent if 0 <= percent <= 100 else None


def extract_brother_l1632w_status_message(html: str) -> list[str]:
    for label, block in definition_pairs(html):
        if normalize_text(label) not in {"estado do dispositivo", "device status"}:
            continue
        candidates = block.moni_chunks or block.chunks
        candidate_text = " ".join(candidates)
        normalized_candidate = normalize_text(candidate_text)
        for message in BROTHER_DCP_L1632W_STATUS_MESSAGES:
            if normalize_text(message) in normalized_candidate:
                return [message]
        if candidate_text:
            return [candidate_text]
    return []


def extract_brother_l1632w_toner_status_metadata(html: str) -> dict[str, object]:
    for label, block in definition_pairs(html):
        normalized_label = normalize_text(label)
        if "toner" not in normalized_label:
            continue
        labels = unique_messages(block.toner_labels)
        if not labels:
            labels = unique_messages(
                [
                    chunk.strip().upper()
                    for chunk in block.chunks
                    if chunk.strip().upper() in TONER_LABELS
                ]
            )
        return {
            "nivel_toner_bloco_detectado": True,
            "nivel_toner_labels": labels,
            "nivel_toner_percentual_disponivel": False,
        }
    chunks = extract_visible_text_chunks(html)
    normalized_text = normalize_text(" ".join(chunks))
    fallback_labels = unique_messages(
        [chunk.strip().upper() for chunk in chunks if chunk.strip().upper() in TONER_LABELS]
    )
    if "toner" in normalized_text and fallback_labels:
        return {
            "nivel_toner_bloco_detectado": True,
            "nivel_toner_labels": fallback_labels,
            "nivel_toner_percentual_disponivel": False,
        }
    return {
        "nivel_toner_bloco_detectado": False,
        "nivel_toner_labels": [],
        "nivel_toner_percentual_disponivel": False,
    }


def parse_brother_dcp_l1632w_maintenance_info(html: str) -> dict[str, int]:
    info: dict[str, int] = {}
    for section, label, value in definition_sections(html):
        normalized_section = normalize_text(section)
        normalized_label = normalize_text(label).replace("*", "")

        if "vida" in normalized_section and "restante" in normalized_section:
            if "unidade de tambor" in normalized_label:
                percent = _extract_percent(value)
                if percent is not None:
                    info["unidade_tambor_percentual"] = percent
            if normalized_label == "toner":
                percent = _extract_percent(value)
                if percent is not None:
                    info["toner_percentual"] = percent

        if (
            "total" in normalized_section
            and "impressas" in normalized_section
            and "a4/letter" in normalized_label
        ):
            total = _extract_first_int(value)
            if total is not None:
                info["total_paginas_impressas_a4_letter"] = total

    return info


class BrotherDcpL1632wStatusParser(HtmlStatusParser):
    parser_name = "brother_dcp_l1632w_status"
    supported_manufacturer = "Brother"
    supported_model = "DCP-L1632W"

    def parse(self, html: str) -> HtmlStatusParseResult:
        messages = self._extract_status_messages(html)
        metadata = extract_brother_l1632w_toner_status_metadata(html)
        if not messages:
            return self.error_result(
                "html_status_nao_encontrado",
                "Estado da maquina nao encontrado no HTML de status.",
                metadados=metadata,
            )
        return self.success_result(
            messages,
            metadados=metadata,
        )

    def _extract_status_messages(self, html: str) -> list[str]:
        structured = extract_brother_l1632w_status_message(html)
        if structured:
            return structured
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
