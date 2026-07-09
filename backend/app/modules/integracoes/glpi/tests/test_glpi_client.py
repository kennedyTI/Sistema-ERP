from unittest import TestCase

from backend.app.modules.integracoes.glpi.clients.glpi_client import (
    GlpiClient,
    sanitize_glpi_data,
)
from backend.app.modules.integracoes.glpi.config import GlpiSettings


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if url.endswith("/initSession"):
            return FakeResponse({"session_token": "sessao-secreta"})
        return FakeResponse({"success": True})

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return FakeResponse({"id": 321, "message": "Chamado criado"}, 201)


class GlpiClientTest(TestCase):
    def setUp(self):
        self.settings = GlpiSettings(
            enabled=True,
            base_url="https://glpi.example.com",
            app_token="app-token-secreto",
            user_token="user-token-secreto",
            verify_ssl=True,
        )

    def test_abre_ticket_com_payload_rest_v1(self):
        session = FakeSession()
        client = GlpiClient(self.settings, session=session)

        result = client.open_ticket({"name": "Chamado", "content": "Descricao"})

        self.assertEqual(result["id"], 321)
        ticket_call = next(call for call in session.calls if call[1].endswith("/Ticket"))
        self.assertEqual(ticket_call[2]["json"], {"input": {"name": "Chamado", "content": "Descricao"}})
        self.assertEqual(ticket_call[2]["headers"]["Session-Token"], "sessao-secreta")
        self.assertTrue(any(call[1].endswith("/killSession") for call in session.calls))

    def test_sanitiza_tokens_em_resposta(self):
        sanitized = sanitize_glpi_data(
            {
                "id": 10,
                "session_token": "segredo",
                "nested": {"Authorization": "valor-ficticio"},
            }
        )

        self.assertEqual(sanitized["session_token"], "[REDACTED]")
        self.assertEqual(sanitized["nested"]["Authorization"], "[REDACTED]")
        self.assertNotIn("segredo", str(sanitized))
