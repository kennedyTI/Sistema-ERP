"""Cliente IPP restrito a estado operacional, sem envio de trabalhos."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from pyipp import IPP
from pyipp.exceptions import IPPConnectionError, IPPError, IPPParseError


IPP_PORT = 631
IPP_PRINT_PATH = "/ipp/print"
IPP_TIMEOUT_SECONDS = 5

STATE_MESSAGES = {
    "idle": "Em espera",
    "processing": "Imprimindo",
    "stopped": "Erro: impressora parada",
}

REASON_MESSAGES = {
    "media-empty": "Sem papel",
    "media-needed": "Carregar papel",
    "media-jam": "Atolamento de papel",
    "toner-low": "Toner baixo",
    "toner-empty": "Sem toner",
    "marker-supply-low": "Suprimento baixo",
    "marker-supply-empty": "Suprimento vazio",
    "door-open": "Porta aberta",
    "cover-open": "Tampa aberta",
    "paused": "Impressora pausada",
    "shutdown": "Impressora desligada",
    "spool-area-full": "Fila de impressao cheia",
}


def _reason_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _split_reason_severity(reason: str) -> tuple[str, str | None]:
    for suffix in ("-error", "-warning", "-report"):
        if reason.endswith(suffix):
            return reason[: -len(suffix)], suffix[1:]
    return reason, None


def _localized_messages(state: Any) -> tuple[list[str], list[str]]:
    state_name = str(getattr(state, "printer_state", "") or "").strip().casefold()
    reasons = _reason_values(getattr(state, "reasons", None))
    messages: list[str] = []

    for reason in reasons:
        normalized_reason = reason.strip().casefold()
        if normalized_reason == "none":
            continue
        base_reason, severity = _split_reason_severity(normalized_reason)
        translated = REASON_MESSAGES.get(base_reason)
        # Sufixo report e informativo; nao deve virar falso alerta operacional.
        if translated and severity != "report":
            messages.append(translated)

    state_message = STATE_MESSAGES.get(state_name)
    if state_message:
        messages.append(state_message)

    return list(dict.fromkeys(messages)), reasons


async def _query_printer(
    host: str,
    *,
    port: int,
    base_path: str,
    timeout_seconds: int,
    client_factory: Callable[..., Any],
) -> dict[str, Any]:
    async with client_factory(
        host,
        port=port,
        base_path=base_path,
        request_timeout=timeout_seconds,
        tls=False,
    ) as ipp:
        printer = await ipp.printer()

    messages, reasons = _localized_messages(printer.state)
    return {
        "sucesso": True,
        "mensagens": messages,
        "estado": str(printer.state.printer_state or ""),
        "motivos": reasons,
    }


def fetch_ipp_printer_status(
    host: str,
    *,
    port: int = IPP_PORT,
    base_path: str = IPP_PRINT_PATH,
    timeout_seconds: int = IPP_TIMEOUT_SECONDS,
    client_factory: Callable[..., Any] = IPP,
) -> dict[str, Any]:
    """Consulta atributos IPP sem expor host ou resposta bruta no resultado."""
    try:
        return asyncio.run(
            _query_printer(
                host,
                port=port,
                base_path=base_path,
                timeout_seconds=timeout_seconds,
                client_factory=client_factory,
            )
        )
    except (TimeoutError, asyncio.TimeoutError):
        return {
            "sucesso": False,
            "erro_codigo": "ipp_timeout",
            "erro_detalhe": "Tempo limite na consulta IPP.",
        }
    except IPPConnectionError:
        return {
            "sucesso": False,
            "erro_codigo": "ipp_conexao",
            "erro_detalhe": "Falha de conexao na consulta IPP.",
        }
    except IPPParseError:
        return {
            "sucesso": False,
            "erro_codigo": "ipp_resposta_invalida",
            "erro_detalhe": "Resposta IPP invalida.",
        }
    except IPPError:
        return {
            "sucesso": False,
            "erro_codigo": "ipp_falha_coleta",
            "erro_detalhe": "Falha na consulta IPP.",
        }
