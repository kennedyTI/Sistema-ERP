from dataclasses import asdict
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from backend.app.modules.printers.monitoring.html_client.models import HtmlClientResponse
from backend.app.modules.printers.monitoring.html_parsers.brother import (
    BrotherDcpL1632wStatusParser,
    extract_visible_text_chunks,
)
from backend.app.modules.printers.monitoring.html_parsers.registry import (
    get_status_parser_for_model,
    parse_html_status_response,
    parse_status_html_for_model,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
BROTHER_STATUS_FIXTURE = FIXTURE_DIR / "brother_dcp_l1632w_status.html"
PROJECT_ROOT = Path(__file__).resolve().parents[7]


class DummyModel:
    def __init__(self, manufacturer="Brother", name="DCP-L1632W"):
        self.manufacturer = manufacturer
        self.name = name


def fixture_html() -> str:
    return BROTHER_STATUS_FIXTURE.read_text(encoding="utf-8")


class BrotherStatusParserTest(TestCase):
    def test_registry_encontra_parser_para_brother_dcp_l1632w(self):
        parser = get_status_parser_for_model(DummyModel())

        self.assertIsInstance(parser, BrotherDcpL1632wStatusParser)

    def test_registry_retorna_erro_controlado_para_modelo_sem_parser(self):
        result = parse_status_html_for_model(DummyModel("HP", "MFP-4303"), fixture_html())

        self.assertFalse(result.sucesso)
        self.assertEqual(result.erro_codigo, "html_status_parser_nao_configurado")
        self.assertNotIn("<html", str(result).lower())

    def test_parser_brother_extrai_estado_em_espera_da_fixture(self):
        result = parse_status_html_for_model(DummyModel(), fixture_html())

        self.assertTrue(result.sucesso)
        self.assertEqual(result.fabricante, "Brother")
        self.assertEqual(result.modelo_nome, "DCP-L1632W")
        self.assertEqual(result.mensagens_brutas, ["Em espera"])
        self.assertEqual(result.mensagens_normalizadas, ["em espera"])
        self.assertEqual(result.estado_principal, "Em espera")
        self.assertIsNone(result.erro_codigo)
        self.assertEqual(result.metadados["parser"], "brother_dcp_l1632w_status")
        self.assertEqual(result.metadados["origem"], "html_status")

    def test_parser_retorna_erro_quando_estado_nao_existe(self):
        result = parse_status_html_for_model(
            DummyModel(),
            "<html><body><h1>Status</h1><p>Sem mensagem operacional.</p></body></html>",
        )

        self.assertFalse(result.sucesso)
        self.assertEqual(result.mensagens_brutas, [])
        self.assertEqual(result.mensagens_normalizadas, [])
        self.assertIsNone(result.estado_principal)
        self.assertEqual(result.erro_codigo, "html_status_nao_encontrado")
        self.assertNotIn("Sem mensagem operacional", str(result))

    def test_parser_tolera_espacos_quebras_e_entidades_html(self):
        html = """
        <html>
          <body>
            <div>Estado</div>
            <strong>
              Em&nbsp;&nbsp;
              espera
            </strong>
          </body>
        </html>
        """

        result = parse_status_html_for_model(DummyModel(), html)

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Em espera"])
        self.assertEqual(result.mensagens_normalizadas, ["em espera"])

    def test_parser_retorna_multiplas_mensagens_quando_existirem(self):
        html = "<html><body><p>Toner baixo</p><p>Tampa aberta</p></body></html>"

        result = parse_status_html_for_model(DummyModel(), html)

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Toner baixo", "Tampa aberta"])
        self.assertEqual(result.mensagens_normalizadas, ["toner baixo", "tampa aberta"])

    def test_parser_ignora_script_style_e_nao_persiste_html_bruto(self):
        html = """
        <html>
          <head>
            <script>document.write("Substituir toner")</script>
            <style>.x { content: "Toner baixo"; }</style>
          </head>
          <body><span>Dormindo</span></body>
        </html>
        """

        chunks = extract_visible_text_chunks(html)
        result = parse_status_html_for_model(DummyModel(), html)

        self.assertEqual(chunks, ["Dormindo"])
        self.assertEqual(result.mensagens_brutas, ["Dormindo"])
        self.assertNotIn("document.write", str(result))

    def test_parser_nao_faz_chamada_de_rede(self):
        with patch("requests.sessions.Session.request") as request:
            result = parse_status_html_for_model(DummyModel(), fixture_html())

        self.assertTrue(result.sucesso)
        request.assert_not_called()

    def test_parser_nao_loga_html_ou_segredos(self):
        html = "<html><body><p>Em espera</p><p>senha-ficticia Authorization Cookie CSRF</p></body></html>"

        with patch("logging.Logger._log") as log_method:
            result = parse_status_html_for_model(DummyModel(), html)

        self.assertTrue(result.sucesso)
        log_method.assert_not_called()

    def test_resultado_nao_inclui_html_bruto_ou_segredos_no_erro(self):
        html = "<html><body>senha-ficticia Cookie Authorization CSRF</body></html>"

        result = parse_status_html_for_model(DummyModel(), html)
        serialized = str(asdict(result))

        self.assertFalse(result.sucesso)
        self.assertNotIn("<html", serialized.lower())
        self.assertNotIn("senha-ficticia", serialized)
        self.assertNotIn("Cookie", serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("CSRF", serialized)

    def test_conveniencia_parseia_resposta_do_cliente_html(self):
        response = HtmlClientResponse(
            sucesso=True,
            status_code=200,
            url_sanitizada="https://10.0.0.10/home/status.html",
            conteudo_html=fixture_html(),
            erro_codigo=None,
            erro_detalhe_sanitizado=None,
            protocolo_usado="https",
            tipo_autenticacao="basic",
        )

        result = parse_html_status_response(DummyModel(), response)

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Em espera"])

    def test_conveniencia_retorna_erro_controlado_para_resposta_invalida(self):
        response = HtmlClientResponse(
            sucesso=False,
            status_code=500,
            url_sanitizada="https://10.0.0.10/home/status.html",
            conteudo_html="<html>erro autenticado</html>",
            erro_codigo="falha_requisicao_html",
            erro_detalhe_sanitizado="HTTP 500",
            protocolo_usado="https",
            tipo_autenticacao="basic",
        )

        result = parse_html_status_response(DummyModel(), response)

        self.assertFalse(result.sucesso)
        self.assertEqual(result.erro_codigo, "html_status_response_invalida")
        self.assertNotIn("erro autenticado", str(result))


class HtmlStatusParserSecurityScopeTest(TestCase):
    def test_fixture_versionada_nao_contem_dados_sensiveis(self):
        content = fixture_html().casefold()

        for forbidden in (
            "senha",
            "password",
            "cookie",
            "authorization",
            "csrf",
            "grupo" + "si" + "mec",
            "si" + "mec",
            "10.",
            "192.168.",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)

    def test_modulo_nao_acessa_banco_nem_requests(self):
        parser_files = [
            PROJECT_ROOT
            / "backend/app/modules/printers/monitoring/html_parsers/base.py",
            PROJECT_ROOT
            / "backend/app/modules/printers/monitoring/html_parsers/brother.py",
            PROJECT_ROOT
            / "backend/app/modules/printers/monitoring/html_parsers/registry.py",
        ]
        content = "\n".join(path.read_text(encoding="utf-8") for path in parser_files)

        self.assertNotIn("requests", content)
        self.assertNotIn(".objects", content)
        self.assertNotIn("Session", content)
        self.assertNotIn("create_engine", content)

    def test_etapa_nao_cria_tabela_nova_ou_cascata(self):
        parser_files = [
            PROJECT_ROOT
            / "backend/app/modules/printers/monitoring/html_parsers/base.py",
            PROJECT_ROOT
            / "backend/app/modules/printers/monitoring/html_parsers/brother.py",
            PROJECT_ROOT
            / "backend/app/modules/printers/monitoring/html_parsers/registry.py",
        ]
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in parser_files
        )

        self.assertNotIn("tentativas_coleta_impressoras", content)
        self.assertNotIn("maquina_id", content)
        self.assertNotIn("sync_machine_alerts_from_collection_result", content)
        self.assertNotIn("collect_and_sync_machine_alerts", content)
        self.assertNotIn("celery_app", content)
