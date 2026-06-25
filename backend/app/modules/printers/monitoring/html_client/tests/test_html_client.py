from unittest import TestCase
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from backend.app.modules.printers.monitoring.html_client.client import (
    build_html_url,
    fetch_html_page,
    parse_brother_login_form,
    protocol_sequence,
    validate_port,
    validate_relative_html_path,
)
from backend.app.modules.printers.monitoring.html_client.exceptions import HtmlClientError
from backend.app.modules.printers.monitoring.html_client.models import HtmlAccessConfig


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


class FakeResponse:
    def __init__(self, status_code=200, text="<html>ok</html>", cookies=None):
        self.status_code = status_code
        self.text = text
        self.cookies = cookies or {}


class FakeSession:
    def __init__(self, *results):
        self.results = list(results)
        self.post_results = []
        self.calls = []
        self.cookies = {}

    def get(self, url, **kwargs):
        self.calls.append({"method": "GET", "url": url, **kwargs})
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def post(self, url, **kwargs):
        self.calls.append({"method": "POST", "url": url, **kwargs})
        result = self.post_results.pop(0)
        if isinstance(result, Exception):
            raise result
        self.cookies.update(getattr(result, "cookies", {}) or {})
        return result


def fixture_html(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def config(**overrides):
    values = {
        "modelo_id": 1,
        "tipo_autenticacao": "basic",
        "usuario": "admin",
        "senha": "senha-ficticia",
        "caminho_status": "/home/status.html",
        "caminho_informacoes": "/general/information.html?kind=item",
        "porta": 80,
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

    def test_monta_url_com_porta_customizada_para_canon(self):
        self.assertEqual(
            build_html_url("10.0.0.10", "http", "/", port=8000),
            "http://10.0.0.10:8000/",
        )

    def test_porta_padrao_80_preserva_url_existente(self):
        self.assertEqual(
            build_html_url("10.0.0.10", "http", "/home/status.html", port=80),
            "http://10.0.0.10/home/status.html",
        )

    def test_rejeita_porta_invalida(self):
        for port in (0, 65536):
            with self.subTest(port=port):
                with self.assertRaises(HtmlClientError):
                    validate_port(port)

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

    def test_cliente_usa_porta_configurada(self):
        session = FakeSession(FakeResponse())

        result = fetch_html_page(
            "10.0.0.10",
            config(protocolo_preferencial="http", porta=8000, caminho_status="/"),
            session=session,
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(session.calls[0]["url"], "http://10.0.0.10:8000/")

    def test_cliente_usa_digest_auth(self):
        session = FakeSession(FakeResponse())

        result = fetch_html_page(
            "10.0.0.10",
            config(tipo_autenticacao="digest", protocolo_preferencial="http"),
            session=session,
        )

        self.assertTrue(result.sucesso)
        self.assertIsInstance(session.calls[0]["auth"], HTTPDigestAuth)

    def test_cookie_retorna_erro_controlado(self):
        session = FakeSession(FakeResponse())

        result = fetch_html_page(
            "10.0.0.10",
            config(tipo_autenticacao="cookie"),
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


class HtmlClientBrotherFormLoginTest(TestCase):
    def test_parser_detecta_container_formulario_logbox_csrf_e_hiddens(self):
        form = parse_brother_login_form(fixture_html("brother_l1632w_login_form.html"))

        self.assertTrue(form.container_detected)
        self.assertTrue(form.form_detected)
        self.assertEqual(form.action, "/home/status.html")
        self.assertEqual(form.method, "post")
        self.assertTrue(form.password_input_detected)
        self.assertEqual(form.password_field_name, "LogBox")
        self.assertTrue(form.csrf_detected)
        self.assertEqual(len(form.hidden_fields), 2)

    def test_login_brother_form_faz_get_post_e_novo_get_status(self):
        session = FakeSession(
            FakeResponse(200, fixture_html("brother_l1632w_login_form.html")),
            FakeResponse(200, fixture_html("brother_l1632w_authenticated_status.html")),
        )
        session.post_results = [FakeResponse(302, "", cookies={"sid": "valor-ficticio"})]

        result = fetch_html_page(
            "10.0.0.10",
            config(tipo_autenticacao="form", protocolo_preferencial="http"),
            session=session,
        )

        self.assertTrue(result.sucesso)
        self.assertIn("Estado do dispositivo", result.conteudo_html)
        self.assertEqual([call["method"] for call in session.calls], ["GET", "POST", "GET"])
        self.assertEqual(session.calls[0]["url"], "http://10.0.0.10/home/status.html")
        self.assertEqual(session.calls[1]["url"], "http://10.0.0.10/home/status.html")
        self.assertEqual(session.calls[2]["url"], "http://10.0.0.10/home/status.html")
        self.assertEqual(session.calls[1]["data"]["LogBox"], "senha-ficticia")
        self.assertIn("CSRFToken", session.calls[1]["data"])
        self.assertEqual(result.metadados["login_container_detected"], True)
        self.assertEqual(result.metadados["login_form_detected"], True)
        self.assertEqual(result.metadados["password_input_detected"], True)
        self.assertEqual(result.metadados["csrf_detected"], True)
        self.assertEqual(result.metadados["hidden_fields_count"], 2)
        self.assertEqual(result.metadados["post_executado"], True)
        self.assertEqual(result.metadados["cookies_recebidos"], True)

    def test_login_brother_form_usa_name_do_logbox_no_payload(self):
        login_html = """
        <div id="LogInOutBox">
          <form method="post" action="/home/status.html">
            <input type="hidden" name="CSRFToken" value="CSRF_SANITIZADO">
            <input id="LogBox" name="senhaAdmin" type="password">
          </form>
        </div>
        """
        session = FakeSession(
            FakeResponse(200, login_html),
            FakeResponse(200, fixture_html("brother_l1632w_authenticated_status.html")),
        )
        session.post_results = [FakeResponse(200, "ok")]

        result = fetch_html_page(
            "10.0.0.10",
            config(tipo_autenticacao="form", protocolo_preferencial="http"),
            session=session,
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(session.calls[1]["data"]["senhaAdmin"], "senha-ficticia")
        self.assertNotIn("LogBox", session.calls[1]["data"])

    def test_login_brother_form_rejeita_action_absoluto_para_host_diferente(self):
        login_html = """
        <div id="LogInOutBox">
          <form method="post" action="http://10.0.0.99/home/status.html">
            <input id="LogBox" name="LogBox" type="password">
          </form>
        </div>
        """
        session = FakeSession(FakeResponse(200, login_html))

        result = fetch_html_page(
            "10.0.0.10",
            config(tipo_autenticacao="form", protocolo_preferencial="http"),
            session=session,
        )

        self.assertFalse(result.sucesso)
        self.assertEqual(result.erro_codigo, "login_form_action_host_invalido")
        self.assertEqual([call["method"] for call in session.calls], ["GET"])

    def test_login_brother_form_aceita_action_relativo_sem_barra(self):
        login_html = """
        <div id="LogInOutBox">
          <form method="post" action="status.html">
            <input id="LogBox" name="LogBox" type="password">
          </form>
        </div>
        """
        session = FakeSession(
            FakeResponse(200, login_html),
            FakeResponse(200, fixture_html("brother_l1632w_authenticated_status.html")),
        )
        session.post_results = [FakeResponse(200, "ok")]

        result = fetch_html_page(
            "10.0.0.10",
            config(tipo_autenticacao="form", protocolo_preferencial="http"),
            session=session,
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(session.calls[1]["url"], "http://10.0.0.10/home/status.html")

    def test_login_brother_form_ausente_trata_como_pagina_ja_autenticada(self):
        session = FakeSession(
            FakeResponse(200, fixture_html("brother_l1632w_authenticated_status.html")),
            FakeResponse(200, fixture_html("brother_l1632w_authenticated_status.html")),
        )

        result = fetch_html_page(
            "10.0.0.10",
            config(tipo_autenticacao="form", protocolo_preferencial="http"),
            session=session,
        )

        self.assertTrue(result.sucesso)
        self.assertEqual([call["method"] for call in session.calls], ["GET", "GET"])
        self.assertFalse(result.metadados["login_form_detected"])
        self.assertFalse(result.metadados["post_executado"])

    def test_login_brother_form_retorna_erro_controlado_sem_logbox(self):
        login_html = """
        <div id="LogInOutBox">
          <form method="post" action="/home/status.html">
            <input type="hidden" name="CSRFToken" value="CSRF_SANITIZADO">
          </form>
        </div>
        """
        session = FakeSession(FakeResponse(200, login_html))

        result = fetch_html_page(
            "10.0.0.10",
            config(tipo_autenticacao="form", protocolo_preferencial="http"),
            session=session,
        )
        serialized = str(result)

        self.assertFalse(result.sucesso)
        self.assertEqual(result.erro_codigo, "login_password_input_nao_detectado")
        self.assertTrue(result.metadados["login_form_detected"])
        self.assertFalse(result.metadados["password_input_detected"])
        self.assertIsNone(result.conteudo_html)
        self.assertNotIn("senha-ficticia", serialized)
        self.assertNotIn("CSRF_SANITIZADO", serialized)
        self.assertNotIn("<form", serialized)

    def test_login_brother_form_nao_retorna_payload_segredos_ou_cookie(self):
        session = FakeSession(
            FakeResponse(200, fixture_html("brother_l1632w_login_form.html")),
            requests.ConnectionError("Cookie Authorization CSRFToken senha-ficticia"),
        )
        session.post_results = [FakeResponse(200, "ok", cookies={"sid": "valor-ficticio"})]

        result = fetch_html_page(
            "10.0.0.10",
            config(tipo_autenticacao="form", protocolo_preferencial="http"),
            session=session,
        )
        serialized = str(result)

        self.assertFalse(result.sucesso)
        self.assertNotIn("senha-ficticia", serialized)
        self.assertNotIn("CSRF_SANITIZADO", serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("Cookie", serialized)
        self.assertNotIn("valor-ficticio", serialized)
        self.assertIsNone(result.conteudo_html)
