from dataclasses import dataclass
from unittest import TestCase

from pyipp.exceptions import IPPConnectionError

from backend.app.modules.printers.monitoring.ipp.client import (
    fetch_ipp_printer_status,
)


@dataclass
class FakeState:
    printer_state: str
    reasons: str | list[str] | None = None
    message: str | None = None


@dataclass
class FakePrinter:
    state: FakeState


class FakeIppClient:
    printer_result = FakePrinter(FakeState("idle"))
    init_kwargs = {}

    def __init__(self, host, **kwargs):
        self.host = host
        type(self).init_kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def printer(self):
        return type(self).printer_result


class FailingIppClient(FakeIppClient):
    async def printer(self):
        raise IPPConnectionError


class IppClientTest(TestCase):
    def test_traduz_estado_idle_sem_expor_motivo_informativo_como_alerta(self):
        FakeIppClient.printer_result = FakePrinter(
            FakeState("idle", reasons="media-empty-report")
        )

        result = fetch_ipp_printer_status(
            "192.0.2.10",
            client_factory=FakeIppClient,
        )

        self.assertTrue(result["sucesso"])
        self.assertEqual(result["mensagens"], ["Em espera"])
        self.assertEqual(result["motivos"], ["media-empty-report"])
        self.assertEqual(FakeIppClient.init_kwargs["port"], 631)
        self.assertEqual(FakeIppClient.init_kwargs["base_path"], "/ipp/print")

    def test_traduz_motivo_de_alerta_e_estado(self):
        FakeIppClient.printer_result = FakePrinter(
            FakeState("stopped", reasons=["toner-low-warning", "media-jam-error"])
        )

        result = fetch_ipp_printer_status(
            "192.0.2.11",
            client_factory=FakeIppClient,
        )

        self.assertEqual(
            result["mensagens"],
            ["Toner baixo", "Atolamento de papel", "Erro: impressora parada"],
        )

    def test_falha_de_conexao_retorna_erro_sanitizado(self):
        result = fetch_ipp_printer_status(
            "192.0.2.12",
            client_factory=FailingIppClient,
        )

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "ipp_conexao")
        self.assertNotIn("192.0.2.12", str(result))
