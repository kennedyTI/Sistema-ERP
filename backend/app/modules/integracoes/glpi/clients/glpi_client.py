"""Cliente seguro para a API REST v1 do GLPI."""

from __future__ import annotations

from typing import Any

import requests

from backend.app.modules.integracoes.glpi.config import GlpiSettings
from backend.app.modules.integracoes.glpi.exceptions import (
    GlpiApiError,
    GlpiResponseError,
)


SENSITIVE_RESPONSE_KEYS = {
    "app-token",
    "authorization",
    "cookie",
    "csrf",
    "session_token",
    "session-token",
    "token",
    "user_token",
}


def sanitize_glpi_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]"
            if str(key).casefold() in SENSITIVE_RESPONSE_KEYS
            else sanitize_glpi_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_glpi_data(item) for item in value]
    return value


class GlpiClient:
    def __init__(
        self,
        settings: GlpiSettings,
        *,
        session: requests.Session | None = None,
    ) -> None:
        settings.validate_for_ticket()
        self.settings = settings
        self.session = session or requests.Session()
        base = settings.base_url.rstrip("/")
        self.api_url = base if base.endswith("/apirest.php") else f"{base}/apirest.php"

    def _json_response(self, response: requests.Response, *, operation: str) -> Any:
        if not 200 <= response.status_code < 300:
            raise GlpiApiError(
                f"GLPI recusou a operacao {operation} (HTTP {response.status_code})."
            )
        try:
            return response.json()
        except ValueError as exc:
            raise GlpiResponseError(
                f"GLPI retornou resposta invalida na operacao {operation}."
            ) from exc

    def _init_session(self) -> str:
        try:
            response = self.session.get(
                f"{self.api_url}/initSession",
                headers={
                    "App-Token": self.settings.app_token,
                    "Authorization": f"user_token {self.settings.user_token}",
                },
                timeout=self.settings.timeout_seconds,
                verify=self.settings.verify_ssl,
            )
        except requests.RequestException as exc:
            raise GlpiApiError("Falha de comunicacao ao autenticar no GLPI.") from exc
        payload = self._json_response(response, operation="initSession")
        session_token = payload.get("session_token") if isinstance(payload, dict) else None
        if not session_token:
            raise GlpiResponseError("GLPI nao retornou token de sessao.")
        return str(session_token)

    def _kill_session(self, session_token: str) -> None:
        try:
            self.session.get(
                f"{self.api_url}/killSession",
                headers={
                    "App-Token": self.settings.app_token,
                    "Session-Token": session_token,
                },
                timeout=self.settings.timeout_seconds,
                verify=self.settings.verify_ssl,
            )
        except requests.RequestException:
            return

    def open_ticket(self, ticket_input: dict[str, Any]) -> dict[str, Any]:
        session_token = self._init_session()
        try:
            try:
                response = self.session.post(
                    f"{self.api_url}/Ticket",
                    headers={
                        "App-Token": self.settings.app_token,
                        "Session-Token": session_token,
                        "Content-Type": "application/json",
                    },
                    json={"input": ticket_input},
                    timeout=self.settings.timeout_seconds,
                    verify=self.settings.verify_ssl,
                )
            except requests.RequestException as exc:
                raise GlpiApiError("Falha de comunicacao ao abrir chamado no GLPI.") from exc
            payload = self._json_response(response, operation="Ticket")
            ticket_id = payload.get("id") if isinstance(payload, dict) else None
            if not isinstance(ticket_id, int):
                raise GlpiResponseError("GLPI nao retornou o identificador do chamado.")
            return sanitize_glpi_data(payload)
        finally:
            self._kill_session(session_token)
