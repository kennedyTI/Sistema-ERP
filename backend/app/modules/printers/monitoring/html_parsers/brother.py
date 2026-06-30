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
    "Trocar toner",
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


@dataclass
class BrotherHtmlAuthSnapshot:
    has_log_in_out_box: bool = False
    has_logbox: bool = False
    has_csrf: bool = False
    has_moni_data: bool = False
    status_moni_messages: list[str] = field(default_factory=list)
    moni_data_chunks: list[str] = field(default_factory=list)
    moni_data_child_tags: list[str] = field(default_factory=list)
    moni_data_child_classes: list[str] = field(default_factory=list)
    has_moni_data_span: bool = False
    has_moni_class: bool = False

    @property
    def has_status_moni(self) -> bool:
        return bool(self.status_moni_messages)

    @property
    def has_operational_status(self) -> bool:
        if self.has_status_moni:
            return True
        return bool(_find_known_messages(
            self.moni_data_chunks,
            BROTHER_DCP_L1632W_STATUS_MESSAGES,
        ))

    def as_auth_state(self) -> dict[str, object]:
        authenticated = self.has_operational_status
        login_required = self.has_logbox and not authenticated
        error_code = None
        if login_required:
            error_code = "html_autenticacao_requerida"
        elif (self.has_moni_data or self.has_log_in_out_box) and not authenticated:
            error_code = "html_sessao_brother_invalida"
        elif not authenticated:
            error_code = "html_status_nao_detectado"
        return {
            "autenticado": authenticated,
            "login_requerido": login_required,
            "tem_log_in_out_box": self.has_log_in_out_box,
            "tem_logbox": self.has_logbox,
            "tem_csrf": self.has_csrf,
            "tem_moni_data": self.has_moni_data,
            "tem_status_moni": self.has_status_moni,
            "tem_moni_class": self.has_moni_class,
            "erro_codigo": error_code,
        }


class BrotherHtmlAuthStateParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.snapshot = BrotherHtmlAuthSnapshot()
        self._ignored_stack: list[str] = []
        self._element_stack: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag, attrs):
        normalized_tag = tag.lower()
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        inside_moni_data = self._inside_moni_data()
        self._element_stack.append((normalized_tag, attrs_dict))
        if normalized_tag in {"script", "style", "noscript"}:
            self._ignored_stack.append(normalized_tag)

        if attrs_dict.get("id") == "LogInOutBox":
            self.snapshot.has_log_in_out_box = True
        if attrs_dict.get("id") == "LogBox":
            self.snapshot.has_logbox = True
        if _is_csrf_name(attrs_dict.get("id")) or _is_csrf_name(attrs_dict.get("name")):
            self.snapshot.has_csrf = True
        if attrs_dict.get("id") == "moni_data":
            self.snapshot.has_moni_data = True
        elif inside_moni_data:
            self.snapshot.moni_data_child_tags.append(normalized_tag)
            if normalized_tag == "span":
                self.snapshot.has_moni_data_span = True
            for class_name in _split_classes(attrs_dict.get("class")):
                self.snapshot.moni_data_child_classes.append(class_name)
            if _class_has_moni(attrs_dict.get("class")):
                self.snapshot.has_moni_class = True

    def handle_endtag(self, tag):
        normalized_tag = tag.lower()
        if self._ignored_stack and self._ignored_stack[-1] == normalized_tag:
            self._ignored_stack.pop()
        for index in range(len(self._element_stack) - 1, -1, -1):
            if self._element_stack[index][0] == normalized_tag:
                del self._element_stack[index:]
                break

    def handle_data(self, data):
        if self._ignored_stack:
            return
        text = " ".join(data.replace("\xa0", " ").split())
        if not text:
            return
        if self._inside_moni_data():
            self.snapshot.moni_data_chunks.append(text)
        if self._inside_moni_status():
            self.snapshot.status_moni_messages.append(text)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def _inside_moni_status(self) -> bool:
        has_moni_data = self._inside_moni_data()
        has_moni_class = any(_class_has_moni(attrs.get("class")) for _tag, attrs in self._element_stack)
        return has_moni_data and has_moni_class

    def _inside_moni_data(self) -> bool:
        return any(attrs.get("id") == "moni_data" for _tag, attrs in self._element_stack)

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


def _is_csrf_name(value: str | None) -> bool:
    return (value or "").casefold() == "csrftoken"


def _split_classes(value: str | None) -> list[str]:
    return [chunk for chunk in (value or "").split() if chunk]


def _class_has_moni(value: str | None) -> bool:
    return any("moni" in class_name.casefold() for class_name in _split_classes(value))


def brother_html_auth_snapshot(html: str) -> BrotherHtmlAuthSnapshot:
    parser = BrotherHtmlAuthStateParser()
    parser.feed(html or "")
    parser.close()
    return parser.snapshot


def classify_brother_html_auth_state(html: str) -> dict[str, object]:
    return brother_html_auth_snapshot(html).as_auth_state()


def extract_brother_moni_status_messages(html: str) -> list[str]:
    snapshot = brother_html_auth_snapshot(html)
    return unique_messages(snapshot.status_moni_messages)


def extract_brother_moni_data_direct_messages(html: str) -> list[str]:
    snapshot = brother_html_auth_snapshot(html)
    return _find_known_messages(snapshot.moni_data_chunks, BROTHER_DCP_L1632W_STATUS_MESSAGES)


def _sanitize_preview(value: str, *, limit: int = 200) -> str:
    preview = " ".join((value or "").replace("\xa0", " ").split())
    preview = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[ip_oculto]", preview)
    preview = re.sub(r"\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b", "[mac_oculto]", preview)
    for marker in ("senha", "password", "authorization", "cookie", "csrf", "token"):
        preview = re.sub(re.escape(marker), "[segredo_oculto]", preview, flags=re.IGNORECASE)
    return preview[:limit]


def detect_brother_l1632w_status_terms(html: str) -> list[str]:
    chunks = extract_visible_text_chunks(html or "")
    return _find_known_messages(chunks, BROTHER_DCP_L1632W_STATUS_MESSAGES)


def build_brother_l1632w_moni_data_debug(html: str) -> dict[str, object]:
    snapshot = brother_html_auth_snapshot(html)
    text = _sanitize_preview(" ".join(snapshot.moni_data_chunks), limit=200)
    return {
        "tem_moni_data": snapshot.has_moni_data,
        "tem_moni_class": snapshot.has_moni_class,
        "tem_span": snapshot.has_moni_data_span,
        "tags_filhas": unique_messages(snapshot.moni_data_child_tags),
        "classes_filhas": unique_messages(snapshot.moni_data_child_classes),
        "texto_visivel_preview": text,
        "texto_visivel_tamanho": len(text),
        "parece_vazio": not bool(text),
    }


def compare_brother_l1632w_moni_shape(html: str) -> dict[str, object]:
    debug = build_brother_l1632w_moni_data_debug(html)
    auth_state = classify_brother_html_auth_state(html)
    terms = detect_brother_l1632w_status_terms(html)
    moni_terms = extract_brother_moni_data_direct_messages(html)

    if auth_state["login_requerido"]:
        cause = "login_requerido"
    elif not debug["tem_moni_data"]:
        cause = "moni_data_ausente"
    elif debug["parece_vazio"]:
        cause = "moni_data_vazio"
    elif debug["tem_moni_class"]:
        cause = "moni_data_com_moni_detectado"
    elif moni_terms:
        cause = "moni_data_com_texto_sem_classe_moni"
    elif auth_state["erro_codigo"] == "html_sessao_brother_invalida":
        cause = "sessao_brother_invalida"
    elif not terms:
        cause = "html_sem_texto_operacional"
    else:
        cause = "moni_data_sem_elemento_moni_no_html_retornado"

    return {
        "expected_shape": {
            "seletor_prioritario": "#moni_data .moni",
            "esperado": True,
        },
        "actual_shape": {
            "tem_moni_data": debug["tem_moni_data"],
            "tem_moni_class": debug["tem_moni_class"],
            "tem_texto_operacional": bool(moni_terms or terms),
        },
        "provavel_causa": cause,
    }


class BrotherMaintenanceMarkerParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.has_dl_items = False
        self.has_dl_items_info_1line = False
        self._ignored_stack: list[str] = []
        self._chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        normalized_tag = tag.lower()
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if normalized_tag in {"script", "style", "noscript"}:
            self._ignored_stack.append(normalized_tag)
        if normalized_tag == "dl":
            classes = set(attrs_dict.get("class", "").split())
            if "items" in classes:
                self.has_dl_items = True
            if "items_info_1line" in classes:
                self.has_dl_items_info_1line = True

    def handle_endtag(self, tag):
        normalized_tag = tag.lower()
        if self._ignored_stack and self._ignored_stack[-1] == normalized_tag:
            self._ignored_stack.pop()

    def handle_data(self, data):
        if self._ignored_stack:
            return
        text = " ".join(data.replace("\xa0", " ").split())
        if text:
            self._chunks.append(text)

    @property
    def normalized_text(self) -> str:
        return normalize_text(" ".join(self._chunks))


def detect_brother_l1632w_maintenance_markers(html: str) -> dict[str, bool]:
    parser = BrotherMaintenanceMarkerParser()
    parser.feed(html or "")
    parser.close()
    text = parser.normalized_text
    return {
        "tem_dl_items": parser.has_dl_items,
        "tem_dl_items_info_1line": parser.has_dl_items_info_1line,
        "tem_unidade_tambor": "unidade de tambor" in text,
        "tem_toner": "toner" in text,
        "tem_contador_paginas": "contador pag" in text,
        "tem_a4_letter": "a4/letter" in text,
    }


def build_brother_l1632w_maintenance_debug(html: str) -> dict[str, object]:
    markers = detect_brother_l1632w_maintenance_markers(html)
    info = parse_brother_dcp_l1632w_maintenance_info(html)
    labels: list[str] = []
    for _section, label, _value in definition_sections(html):
        normalized_label = normalize_text(label).replace("*", "")
        if "contador pag" in normalized_label:
            labels.append("Contador pag.")
        if "unidade de tambor" in normalized_label:
            labels.append("Unidade de tambor*")
        if normalized_label == "toner":
            labels.append("Toner**")
        if "a4/letter" in normalized_label:
            labels.append("A4/Letter")
    return {
        "tem_dl_items": markers["tem_dl_items"],
        "tem_dl_items_info_1line": markers["tem_dl_items_info_1line"],
        "labels_detectados": unique_messages(labels),
        "campos_extraidos": {
            "contador_paginas": "contador_paginas" in info,
            "total_paginas_impressas_a4_letter": "total_paginas_impressas_a4_letter" in info,
            "unidade_tambor_percentual": "unidade_tambor_percentual" in info,
            "toner_percentual": "toner_percentual" in info,
        },
    }


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
        has_moni_class = any(_class_has_moni(attrs.get("class")) for _tag, attrs in self._element_stack)
        return has_moni_data and has_moni_class


def parse_definition_blocks(html: str) -> list[HtmlDefinitionBlock]:
    parser = DefinitionItemsParser()
    parser.feed(html or "")
    parser.close()
    return parser.blocks


class BrotherTonerIndicatorParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.has_low_toner = False
        self._element_stack: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag, attrs):
        normalized_tag = tag.lower()
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        self._element_stack.append((normalized_tag, attrs_dict))
        if normalized_tag != "img" or not self._inside_ink_level():
            return

        image_source = attrs_dict.get("src", "").casefold()
        image_alt = normalize_text(attrs_dict.get("alt"))
        self.has_low_toner = self.has_low_toner or (
            image_source.endswith("low.gif") or image_alt == "low"
        )

    def handle_endtag(self, tag):
        normalized_tag = tag.lower()
        for index in range(len(self._element_stack) - 1, -1, -1):
            if self._element_stack[index][0] == normalized_tag:
                del self._element_stack[index:]
                break

    def _inside_ink_level(self) -> bool:
        return any(
            attrs.get("id") == "ink_level"
            for _tag, attrs in self._element_stack
        )


def brother_has_low_toner_indicator(html: str) -> bool:
    parser = BrotherTonerIndicatorParser()
    parser.feed(html or "")
    parser.close()
    return parser.has_low_toner


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
    moni_messages = extract_brother_moni_status_messages(html)
    if moni_messages:
        return moni_messages
    direct_messages = extract_brother_moni_data_direct_messages(html)
    if direct_messages:
        return direct_messages

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

        if "contador pag" in normalized_label:
            total = _extract_first_int(value)
            if total is not None:
                info["contador_paginas"] = total

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
        auth_state = classify_brother_html_auth_state(html)
        messages = self._extract_status_messages(html)
        metadata = {
            **extract_brother_l1632w_toner_status_metadata(html),
            "auth_state": auth_state,
        }
        if auth_state["login_requerido"] and not auth_state["autenticado"]:
            return self.error_result(
                "html_autenticacao_requerida",
                "Pagina Brother retornou formulario de login.",
                metadados=metadata,
            )
        if not messages:
            return self.error_result(
                str(auth_state["erro_codigo"] or "html_status_nao_detectado"),
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
        messages = focused or _find_known_messages(
            chunks,
            BROTHER_DCP_L2540DW_STATUS_MESSAGES,
        )
        if brother_has_low_toner_indicator(html):
            messages.append("Subs. toner")
        return unique_messages(messages)
