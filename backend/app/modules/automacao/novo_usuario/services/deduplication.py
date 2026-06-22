"""Helpers de deduplicacao por UIDL e Message-ID."""

from __future__ import annotations


DeduplicationFilter = tuple[tuple[str, str], ...]


def build_deduplication_filter(
    uidl: str | None,
    message_id: str | None,
) -> DeduplicationFilter | None:
    filters: list[tuple[str, str]] = []
    if uidl:
        filters.append(("uidl_email", uidl))
    if message_id:
        filters.append(("message_id_email", message_id))
    return tuple(filters) or None
