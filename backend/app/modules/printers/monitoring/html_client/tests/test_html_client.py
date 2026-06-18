from unittest import TestCase

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from backend.app.modules.printers.monitoring.html_client.client import (
    build_html_url,
    fetch_html_page,
    protocol_sequence,
    validate_relative_html_path,
)
from backend.app.modules.printers.monitoring.html_client.exceptions import HtmlClientError
from backend.app.modules.printers.monitoring.html_client.models import HtmlAccessConfig


class FakeResponse:
    def __init__(self, status_code=200, text="<html>ok</html>"):
        self.status_code = status_code
        self.text = text


class FakeSession:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def config(**overrides):
    values = {
        "modelo_id": 1,
        "tipo_autenticacao": "basic",
        "usuario": "admin",
        "senha": "senha-ficticia",
        "caminho_status": "/home/status.html",
        "caminho_informacoes": "/general/information.html?kind=item",
        "timeout_segundos": 5,
        "protocolo_preferencial": "auto",
        "validar_ssl": False,
    }
    values.update(overrides)
    return HtmlAccessConfig(**values)


class HtmlClientPathTest(TestCase):
    def test_aceita_caminho_relativo_e_query_string(self):
        self.assertEqual(validate_relative_html_path("/home/status.html"), "/home/status.html")
        self.assertEqual(
            validate_relative_html_path("/general/information.html?kind=item"),
            "/general/information.html?kind=item",
        )
        self.assertIsNone(validate_relative_html_path(None))

    def test_rejeita_url_absoluta_ou_protocol_relative(self):
        for path in (
            "http://10.0.0.1/home/status.html",
            "https://10.0.0.1/home/status.html",
            "//10.0.0.1/home/status.html",
            "home/status.html",
        ):
            with self.subTest(path=path):
                with self.assertRaises(HtmlClientError):
                    validate_relative_html_path(path)

    def test_monta_urls_http_e_https_com_ip_da_maquina(self):
        self.assertEqual(
            build_html_url("10.0.0.10", "http", "/home/status.html"),
            "http://10.0.0.10/home/status.html",
        )
        self.assertEqual(
            build_html_url("10.0.0.10", "https", "/home/status.html"),
            "https://10.0.0.10/home/status.html",
        )

    def test_rejeita_protocolo_na_montagem_de_url_concreta(self):
        with self.assertRaises(HtmlClientError):
            build_html_url("10.0.0.10", "auto", "/home/status.html")

    def test_protocolo_auto_tenta_https_antes_de_http(self):
        self.assertEqual(protocol_sequence("auto"), ("https", "http"))
        self.assertEqual(protocol_sequence("http"), ("http",))
        self.assertEqual(protocol_sequence("https"), ("https",))


class HtmlClientRequestTest(TestCase):
    def test_auto_cai_para_http_se_https_falhar(self):
        session = FakeSession(
            requests.ConnectionError("falha https com segredo"),
            FakeResponse(200, "<html>http</html>"),
        )

        result = fetch_html_page("10.0.0.10", config(), session=session)

        self.assertTrue(result.sucesso)
        self.assertEqual(result.protocolo_usado, "http")
        self.assertEqual(session.calls[0]["url"], "https://10.0.0.10/home/status.html")
        self.assertEqual(session.calls[1]["url"], "http://10.0.0.10/home/status.html")

    def test_https_nao_tenta_http_quando_preferencial_e_https(self):
        session = FakeSession(requests.Timeout("timeout"))

        result = fetch_html_page(
            "10.0.0.10",
            config(protocolo_preferencial="https"),
            session=session,
        )

        self.assertFalse(result.sucesso)
        self.assertEqual(result.protocolo_usado, "https")
        self.assertEqual(len(session.calls), 1)

    def test_http_nao_tenta_https_quando_preferencial_e_http(self):
        session = FakeSession(FakeResponse(200, "<html>http</html>"))

        result = fetch_html_page(
            "10.0.0.10",
            config(protocolo_preferencial="http"),
            session=session,
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(result.protocolo_usado, "http")
        self.assertEqual(len(session.calls), 1)

    def test_cliente_usa_timeout_validar_ssl_e_basic_auth(self):
        session = FakeSession(FakeResponse())

        result = fetch_html_page(
            "10.0.0.10",
            config(protocolo_preferencial="https", validar_ssl=True, timeout_segundos=7),
            session=session,
        )

        self.assertTrue(result.sucesso)
        call = session.calls[0]
        self.assertEqual(call["timeout"], 7)
        self.assertTrue(call["verify"])
        self.assertIsInstance(call["auth"], HTTPBasicAuth)

    def test_cliente_usa_digest_auth(self):
        session = FakeSession(FakeResponse())

        result = fetch_html_page(
            "10.0.0.10",
            config(tipo_autenticacao="digest", protocolo_preferencial="http"),
            session=session,
        )

        self.assertTrue(result.sucesso)
        self.assertIsInstance(session.calls[0]["auth"], HTTPDigestAuth)

    def test_form_e_cookie_retornam_erro_controlado(self):
        for auth_type in ("form", "cookie"):
            with self.subTest(auth_type=auth_type):
                session = FakeSession(FakeResponse())

                result = fetch_html_page(
                    "10.0.0.10",
                    config(tipo_autenticacao=auth_type),
                    session=session,
                )

                self.assertFalse(result.sucesso)
                self.assertEqual(
                    result.erro_codigo,
                    "autenticacao_nao_suportada_nesta_etapa",
                )
                self.assertEqual(session.calls, [])

    def test_ip_invalido_retorna_erro_controlado(self):
        session = FakeSession(FakeResponse())

        result = fetch_html_page("painel.local", config(), session=session)

        self.assertFalse(result.sucesso)
        self.assertEqual(result.erro_codigo, "ip_maquina_invalido")
        self.assertEqual(session.calls, [])

    def test_cliente_nao_retorna_segredos_em_falha(self):
        encrypted_marker = "gAAAA-token-criptografado-ficticio"
        session = FakeSession(requests.ConnectionError("Authorization Cookie senha-ficticia"))

        result = fetch_html_page(
            "10.0.0.10",
            config(protocolo_preferencial="https"),
            session=session,
        )
        serialized = str(result)

        self.assertNotIn("senha-ficticia", serialized)
        self.assertNotIn(encrypted_marker, serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("Cookie", serialized)
        self.assertIsNone(result.conteudo_html)

    def test_cliente_nao_persiste_html_e_nao_expande_html_em_erro(self):
        session = FakeSession(FakeResponse(500, "<html>conteudo bruto autenticado</html>"))

        result = fetch_html_page("10.0.0.10", config(protocolo_preferencial="http"), session=session)

        self.assertFalse(result.sucesso)
        self.assertIsNone(result.conteudo_html)
        self.assertNotIn("conteudo bruto autenticado", str(result))
