"""Leitura POP3 dos e-mails recentes de admissao."""

from __future__ import annotations

import poplib
from dataclasses import dataclass
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import Message
from email.policy import default
from email.utils import getaddresses, parsedate_to_datetime
from typing import Iterable

from backend.app.core.timezone import SAO_PAULO_ZONE, aware_now_sao_paulo
from backend.app.modules.automacao.novo_usuario.config import (
    NovoUsuarioAutomationSettings,
)
from backend.app.modules.automacao.novo_usuario.services.admission_email_parser import (
    html_to_visible_text,
)
from backend.app.modules.automacao.novo_usuario.services.credentials_service import (
    NovoUsuarioCredentials,
)


@dataclass(frozen=True)
class POP3EmailRecord:
    uidl: str | None
    message_id: str | None
    sender: str
    recipient: str
    subject: str
    date: datetime
    body: str


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value))).strip()


def _addresses(value: str | None) -> str:
    addresses = getaddresses([value or ""])
    return ", ".join(email for _name, email in addresses if email)


def _message_date(message: Message) -> datetime | None:
    raw_date = message.get("Date")
    if not raw_date:
        return None
    parsed = parsedate_to_datetime(raw_date)
    if parsed.tzinfo is not None:
        return parsed.astimezone(SAO_PAULO_ZONE).replace(tzinfo=None)
    return parsed


def _message_text(message: Message) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if message.is_multipart():
        parts: Iterable[Message] = message.walk()
    else:
        parts = (message,)

    for part in parts:
        if part.is_multipart():
            continue
        disposition = (part.get_content_disposition() or "").lower()
        if disposition == "attachment":
            continue
        content_type = part.get_content_type()
        try:
            content = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")

        if content_type == "text/plain":
            plain_parts.append(str(content))
        elif content_type == "text/html":
            html_parts.append(html_to_visible_text(str(content)))

    if plain_parts:
        return "\n".join(plain_parts).strip()
    return "\n".join(html_parts).strip()


def _parse_uidl_lines(lines: list[bytes]) -> dict[int, str]:
    uidls: dict[int, str] = {}
    for line in lines:
        parts = line.decode("utf-8", errors="replace").split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            uidls[int(parts[0])] = parts[1].strip()
    return uidls


class POP3EmailReader:
    def __init__(self, settings: NovoUsuarioAutomationSettings):
        self.settings = settings

    def fetch_recent(
        self,
        credentials: NovoUsuarioCredentials,
        *,
        now: datetime | None = None,
    ) -> list[POP3EmailRecord]:
        if not self.settings.pop_ssl:
            raise RuntimeError("A automacao foi configurada para exigir POP3 com SSL.")

        current_time = (now or aware_now_sao_paulo()).replace(tzinfo=None)
        window_start = current_time - timedelta(
            minutes=self.settings.email_lookback_minutes
        )

        client = poplib.POP3_SSL(self.settings.pop_host, self.settings.pop_port)
        try:
            client.user(credentials.email)
            client.pass_(credentials.email_password)
            _response, uidl_lines, _octets = client.uidl()
            uidls = _parse_uidl_lines(uidl_lines)
            message_count = len(uidls)
            start_index = max(1, message_count - self.settings.pop_max_emails + 1)
            records: list[POP3EmailRecord] = []

            for index in range(message_count, start_index - 1, -1):
                _response, lines, _octets = client.retr(index)
                raw_message = b"\r\n".join(lines)
                message = message_from_bytes(raw_message, policy=default)
                message_date = _message_date(message)
                if message_date is None:
                    continue
                if not window_start <= message_date <= current_time:
                    continue

                records.append(
                    POP3EmailRecord(
                        uidl=uidls.get(index),
                        message_id=_decode_header_value(message.get("Message-ID")),
                        sender=_addresses(message.get("From")),
                        recipient=_addresses(message.get("To")),
                        subject=_decode_header_value(message.get("Subject")),
                        date=message_date,
                        body=_message_text(message),
                    )
                )
            return records
        finally:
            try:
                client.quit()
            except Exception:
                client.close()
