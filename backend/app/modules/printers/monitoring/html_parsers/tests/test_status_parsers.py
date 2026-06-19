from dataclasses import asdict
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from backend.app.modules.printers.monitoring.html_client.models import HtmlClientResponse
from backend.app.modules.printers.monitoring.html_parsers.brother import (
    BrotherDcpL1632wStatusParser,
    BrotherDcpL2540dwStatusParser,
    extract_visible_text_chunks,
)
from backend.app.modules.printers.monitoring.html_parsers.canon import (
    CanonIrC3326iStatusParser,
)
from backend.app.modules.printers.monitoring.html_parsers.hp import HpMfp4303StatusParser
from backend.app.modules.printers.monitoring.html_parsers.registry import (
    get_status_parser_for_model,
    parse_html_status_response,
    parse_status_html_for_model,
)
from backend.app.modules.printers.monitoring.html_parsers.samsung import (
    SamsungK4350StatusParser,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
PROJECT_ROOT = Path(__file__).resolve().parents[7]


class DummyModel:
    def __init__(self, manufacturer="Brother", name="DCP-L1632W"):
        self.manufacturer = manufacturer
        self.name = name


def fixture_html(name: str = "brother_dcp_l1632w_status.html") -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class HtmlStatusParserByModelTest(TestCase):
    def test_parser_brother_l1632w_extrai_subs_o_toner(self):
        result = parse_status_html_for_model(DummyModel(), fixture_html())

        self.assertTrue(result.sucesso)
        self.assertEqual(result.fabricante, "Brother")
        self.assertEqual(result.modelo_nome, "DCP-L1632W")
        self.assertEqual(result.mensagens_brutas, ["Subs. o toner"])
        self.assertEqual(result.mensagens_normalizadas, ["subs. o toner"])
        self.assertEqual(result.estado_principal, "Subs. o toner")
        self.assertEqual(result.metadados["parser"], "brother_dcp_l1632w_status")

    def test_parser_brother_l2540dw_extrai_ha_pouco_toner(self):
        result = parse_status_html_for_model(
            DummyModel("Brother", "DCP-L2540DW"),
            fixture_html("brother_dcp_l2540dw_status.html"),
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Há pouco toner"])
        self.assertEqual(result.mensagens_normalizadas, ["ha pouco toner"])
        self.assertEqual(result.estado_principal, "Há pouco toner")

    def test_parser_canon_extrai_erros_sem_usar_scanner_como_principal(self):
        result = parse_status_html_for_model(
            DummyModel("Canon", "IR-C3326I"),
            fixture_html("canon_ir_c3326i_status.html"),
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(result.estado_principal, "Ocorreu um erro.")
        self.assertIn("Ocorreu um erro.", result.mensagens_brutas)
        self.assertIn("O toner Magenta está baixo.", result.mensagens_brutas)
        self.assertIn("O toner Amarelo está baixo.", result.mensagens_brutas)
        self.assertIn("Poderá ter ocorrido um erro.", result.mensagens_brutas)
        self.assertNotEqual(result.estado_principal, "Modo de espera.")
        self.assertNotIn("Modo de espera.", result.mensagens_brutas)

    def test_parser_samsung_extrai_estado_e_alerta(self):
        result = parse_status_html_for_model(
            DummyModel("Samsung", "K-4350"),
            fixture_html("samsung_k4350_status.html"),
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Erro", "1 Alerta(s) ocorridos"])
        self.assertEqual(
            result.mensagens_normalizadas,
            ["erro", "1 alerta(s) ocorridos"],
        )
        self.assertEqual(result.estado_principal, "Erro")

    def test_parser_hp_extrai_bandejas_e_prioriza_aviso(self):
        result = parse_status_html_for_model(
            DummyModel("HP", "MFP-4303"),
            fixture_html("hp_mfp_4303_status.html"),
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(
            result.mensagens_brutas,
            [
                "Band. 1 Qualquer tipo Qualquer tamanho - Aviso",
                "Band. 2 Comum A4 (210 x 297 mm) - OK",
            ],
        )
        self.assertEqual(result.estado_principal, "Aviso")
        self.assertIn(
            "band. 1 qualquer tipo qualquer tamanho - aviso",
            result.mensagens_normalizadas,
        )
        self.assertIn("band. 2 comum a4 (210 x 297 mm) - ok", result.mensagens_normalizadas)

    def test_parser_brother_tolera_espacos_quebras_e_entidades_html(self):
        html = """
        <html>
          <body>
            <div>Estado do dispositivo</div>
            <strong>
              Subs.&nbsp;&nbsp;
              o toner
            </strong>
          </body>
        </html>
        """

        result = parse_status_html_for_model(DummyModel(), html)

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Subs. o toner"])

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


class HtmlStatusParserRegistryTest(TestCase):
    def test_registry_encontra_parsers_suportados(self):
        cases = (
            (DummyModel("Brother", "DCP-L1632W"), BrotherDcpL1632wStatusParser),
            (DummyModel("Brother", "DCP-L2540DW"), BrotherDcpL2540dwStatusParser),
            (DummyModel("Canon", "IR-C3326I"), CanonIrC3326iStatusParser),
            (DummyModel("Samsung", "K-4350"), SamsungK4350StatusParser),
            (DummyModel("Samsung", "K4250LX"), SamsungK4350StatusParser),
            (DummyModel("HP", "MFP-4303"), HpMfp4303StatusParser),
        )

        for model, expected_class in cases:
            with self.subTest(model=model.name):
                self.assertIsInstance(get_status_parser_for_model(model), expected_class)

    def test_registry_retorna_erro_controlado_para_modelo_sem_parser(self):
        result = parse_status_html_for_model(
            DummyModel("HP", "MFP-4305"),
            fixture_html(),
        )

        self.assertFalse(result.sucesso)
        self.assertEqual(result.erro_codigo, "html_status_parser_nao_configurado")
        self.assertNotIn("<html", str(result).lower())

    def test_conveniencia_parseia_resposta_do_cliente_html(self):
        response = HtmlClientResponse(
            sucesso=True,
            status_code=200,
            url_sanitizada="https://equipamento.local/home/status.html",
            conteudo_html=fixture_html(),
            erro_codigo=None,
            erro_detalhe_sanitizado=None,
            protocolo_usado="https",
            tipo_autenticacao="basic",
        )

        result = parse_html_status_response(DummyModel(), response)

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Subs. o toner"])

    def test_conveniencia_retorna_erro_controlado_para_resposta_invalida(self):
        response = HtmlClientResponse(
            sucesso=False,
            status_code=500,
            url_sanitizada="https://equipamento.local/home/status.html",
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
    def test_fixtures_versionadas_nao_contem_dados_sensiveis(self):
        content = "\n".join(path.read_text(encoding="utf-8") for path in FIXTURE_DIR.glob("*.html"))
        content_casefold = content.casefold()

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
            "mac:",
            "uuid",
            "numero de serie",
            "número de série",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content_casefold)

    def test_parsers_nao_fazem_chamada_de_rede(self):
        with patch("requests.sessions.Session.request") as request:
            result = parse_status_html_for_model(DummyModel(), fixture_html())

        self.assertTrue(result.sucesso)
        request.assert_not_called()

    def test_parsers_nao_logam_html_ou_segredos(self):
        html = "<html><body><p>Subs. o toner</p><p>senha-ficticia Authorization Cookie CSRF</p></body></html>"

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

    def test_modulo_nao_acessa_banco_nem_requests(self):
        parser_files = [
            PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/base.py",
            PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/brother.py",
            PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/canon.py",
            PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/hp.py",
            PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/samsung.py",
            PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/registry.py",
        ]
        content = "\n".join(path.read_text(encoding="utf-8") for path in parser_files)

        self.assertNotIn("requests", content)
        self.assertNotIn(".objects", content)
        self.assertNotIn("Session", content)
        self.assertNotIn("create_engine", content)

    def test_etapa_nao_cria_tabela_nova_ou_cascata(self):
        parser_files = [
            PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/base.py",
            PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/brother.py",
            PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/canon.py",
            PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/hp.py",
            PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/samsung.py",
            PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/registry.py",
        ]
        content = "\n".join(path.read_text(encoding="utf-8") for path in parser_files)

        self.assertNotIn("tentativas_coleta_impressoras", content)
        self.assertNotIn("maquina_id", content)
        self.assertNotIn("sync_machine_alerts_from_collection_result", content)
        self.assertNotIn("collect_and_sync_machine_alerts", content)
        self.assertNotIn("celery_app", content)
