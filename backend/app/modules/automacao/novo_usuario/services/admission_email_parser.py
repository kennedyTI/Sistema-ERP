"""Parser do e-mail padrao de admissao."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser


class AdmissionEmailParseError(ValueError):
    """Falha de validacao do corpo do e-mail de admissao."""


@dataclass(frozen=True)
class AdmissionData:
    pn: str
    nome_completo: str
    cargo: str
    unid_org: str
    data_admissao: date

    @property
    def data_admissao_formatada(self) -> str:
        return self.data_admissao.strftime("%d/%m/%Y")


class _VisibleTextParser(HTMLParser):
    block_tags = {"br", "p", "div", "tr", "table", "thead", "tbody", "tfoot", "li"}
    cell_tags = {"td", "th"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001, ARG002
        if tag.lower() in self.block_tags | self.cell_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.block_tags | self.cell_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if data and data.strip():
            self.parts.append(data)

    def text(self) -> str:
        return "\n".join(_clean_line(part) for part in self.parts if _clean_line(part))


FIELD_PATTERNS: tuple[tuple[str, str], ...] = (
    ("pn", r"\bPN\s*:"),
    ("nome_completo", r"\bNOME\s*:"),
    ("cargo", r"\bCARGO\s*:"),
    ("unid_org", r"\bUNID\s*\.?\s*ORG\s*\.?\s*:"),
    ("data_admissao", r"\bDATA\s+ADMISSAO\s*:"),
)

REQUIRED_FIELDS = {
    "pn": "PN",
    "nome_completo": "NOME",
    "cargo": "CARGO",
    "unid_org": "UNID. ORG.",
    "data_admissao": "DATA ADMISSAO",
}


def _clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def _fold_preserving_length(value: str) -> str:
    folded_chars: list[str] = []
    for char in value:
        normalized = unicodedata.normalize("NFKD", char)
        base = "".join(part for part in normalized if not unicodedata.combining(part))
        folded_chars.append((base[:1] or " ").upper())
    return "".join(folded_chars)


def _normalize_label(value: str) -> str:
    folded = _fold_preserving_length(value)
    folded = re.sub(r"[^A-Z0-9]+", " ", folded)
    return re.sub(r"\s+", " ", folded).strip()


def html_to_visible_text(body: str) -> str:
    if not body:
        return ""
    if not re.search(r"<[a-zA-Z][^>]*>", body):
        return unescape(body)

    parser = _VisibleTextParser()
    parser.feed(body)
    return parser.text()


def _find_field_spans(text: str) -> dict[str, str]:
    folded = _fold_preserving_length(text)
    matches: list[tuple[str, re.Match[str]]] = []
    for key, pattern in FIELD_PATTERNS:
        for match in re.finditer(pattern, folded, flags=re.IGNORECASE):
            matches.append((key, match))

    matches.sort(key=lambda item: item[1].start())
    values: dict[str, str] = {}
    for index, (key, match) in enumerate(matches):
        value_start = match.end()
        value_end = matches[index + 1][1].start() if index + 1 < len(matches) else len(text)
        value = text[value_start:value_end].strip(" \t\r\n:-")
        value = _clean_line(value)
        if value:
            values.setdefault(key, value)
    return values


def _label_key(value: str) -> str | None:
    normalized = _normalize_label(value)
    return {
        "PN": "pn",
        "NOME": "nome_completo",
        "CARGO": "cargo",
        "UNID ORG": "unid_org",
        "DATA ADMISSAO": "data_admissao",
    }.get(normalized)


def _find_fields_by_lines(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    pending_key: str | None = None
    lines = [_clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    for line in lines:
        if ":" in line:
            label, value = line.split(":", 1)
            key = _label_key(label)
            if key:
                cleaned_value = _clean_line(value)
                if cleaned_value:
                    values.setdefault(key, cleaned_value)
                    pending_key = None
                else:
                    pending_key = key
                continue

        key = _label_key(line.rstrip(":"))
        if key:
            pending_key = key
            continue

        if pending_key:
            values.setdefault(pending_key, line)
            pending_key = None

    return values


def _parse_admission_date(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except ValueError as exc:
        raise AdmissionEmailParseError(
            f"DATA ADMISSAO invalida: {value}"
        ) from exc


def parse_admission_email_body(body: str) -> AdmissionData:
    text = html_to_visible_text(body)
    values = _find_field_spans(text)
    values.update({key: value for key, value in _find_fields_by_lines(text).items() if key not in values})

    missing = [
        label
        for key, label in REQUIRED_FIELDS.items()
        if not values.get(key)
    ]
    if missing:
        raise AdmissionEmailParseError(
            "Campos obrigatorios ausentes no e-mail de admissao: "
            + ", ".join(missing)
        )

    return AdmissionData(
        pn=values["pn"].strip(),
        nome_completo=values["nome_completo"].strip(),
        cargo=values["cargo"].strip(),
        unid_org=values["unid_org"].strip(),
        data_admissao=_parse_admission_date(values["data_admissao"]),
    )


def subject_matches_prefix(subject: str, prefix: str) -> bool:
    return _fold_preserving_length(subject or "").startswith(
        _fold_preserving_length(prefix or "")
    )
