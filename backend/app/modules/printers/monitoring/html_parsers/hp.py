"""Parser HTML de status para modelos HP."""

from backend.app.modules.printers.monitoring.html_parsers.base import (
    HtmlStatusParseResult,
    HtmlStatusParser,
    unique_messages,
)
from backend.app.modules.printers.monitoring.html_parsers.brother import (
    extract_visible_text_chunks,
)
from backend.app.modules.printers.monitoring.state.rules import normalize_text


HP_STATUS_TERMS = ("erro", "aviso", "ok", "pronto")


class HpMfp4303StatusParser(HtmlStatusParser):
    parser_name = "hp_mfp_4303_status"
    supported_manufacturer = "HP"
    supported_model = "MFP-4303"

    def parse(self, html: str) -> HtmlStatusParseResult:
        messages = self._extract_status_messages(html)
        if not messages:
            return self.error_result(
                "html_status_nao_encontrado",
                "Estados operacionais dos cards nao encontrados no HTML.",
            )
        return self.success_result(messages, estado_principal=self._primary_card_status(messages))

    def _extract_status_messages(self, html: str) -> list[str]:
        chunks = extract_visible_text_chunks(html)
        messages: list[str] = []
        index = 0

        while index < len(chunks):
            chunk = chunks[index]
            normalized = normalize_text(chunk)
            if not normalized.startswith(("band.", "bandeja")):
                index += 1
                continue

            parts = [chunk]
            index += 1
            while index < len(chunks) and not normalize_text(chunks[index]).startswith(
                ("band.", "bandeja")
            ):
                parts.append(chunks[index])
                status_found = self._extract_status_word(chunks[index])
                index += 1
                if status_found:
                    break
            messages.append(self._format_tray_message(parts))

        return unique_messages(messages)

    def _format_tray_message(self, parts: list[str]) -> str:
        status = self._extract_status_word(" ".join(parts))
        body = " ".join(
            part
            for part in parts
            if normalize_text(part)
            not in {
                normalize_text(status),
                "status",
                "papel",
                "cartuchos",
            }
        )
        if status and f"- {status}" not in body:
            return f"{body} - {status}"
        return body

    def _extract_status_word(self, value: str) -> str | None:
        normalized = normalize_text(value)
        for term in HP_STATUS_TERMS:
            if term in normalized:
                if term == "ok":
                    return "OK"
                return term.title()
        return None

    def _primary_card_status(self, messages: list[str]) -> str | None:
        normalized = " ".join(normalize_text(message) for message in messages)
        if "erro" in normalized:
            return "Erro"
        if "aviso" in normalized:
            return "Aviso"
        if "ok" in normalized:
            return "OK"
        if "pronto" in normalized:
            return "Pronto"
        return None
