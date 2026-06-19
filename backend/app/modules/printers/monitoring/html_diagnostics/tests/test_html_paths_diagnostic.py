import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from cryptography.fernet import Fernet

from backend.app.modules.printers.monitoring.html_client.models import HtmlClientResponse
from backend.app.modules.printers.monitoring.html_credentials.crypto import encrypt_password
from backend.app.modules.printers.monitoring.html_diagnostics.diagnostic import (
    build_markdown,
    build_model_matrix,
    build_report,
    detect_information_capabilities,
    diagnose_information_path,
    diagnose_status_path,
    filter_candidate_rows,
    select_diagnostic_targets,
    write_reports,
)


PROJECT_ROOT = Path(__file__).resolve().parents[7]


def status_html(message="Em espera"):
    return f"<html><body><table><tr><td>{message}</td></tr></table></body></html>"


def information_html():
    return """
    <html>
      <body>
        <dl>
          <dt>Modelo</dt><dd>DCP-L1632W</dd>
          <dt>Numero de serie</dt><dd>EXEMPLO</dd>
          <dt>Firmware</dt><dd>1.0</dd>
          <dt>Contador total</dt><dd>123</dd>
          <dt>Toner</dt><dd>OK</dd>
          <dt>Tambor</dt><dd>OK</dd>
          <dt>Papel</dt><dd>A4</dd>
          <dt>Bandejas</dt><dd>Bandeja 1</dd>
          <dt>Duplex</dt><dd>Sim</dd>
          <dt>Digitalizacoes</dt><dd>10</dd>
          <dt>Erros</dt><dd>Nenhum</dd>
        </dl>
      </body>
    </html>
    """


class FakeFetcher:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def __call__(self, ip_value, config, *, page_type="status", session=None):
        self.calls.append(
            {
                "ip": ip_value,
                "page_type": page_type,
                "tipo_autenticacao": config.tipo_autenticacao,
                "timeout_segundos": config.timeout_segundos,
                "porta": config.porta,
                "validar_ssl": config.validar_ssl,
                "protocolo_preferencial": config.protocolo_preferencial,
            }
        )
        if self.responses:
            return self.responses.pop(0)
        html = status_html() if page_type == "status" else information_html()
        return HtmlClientResponse(
            sucesso=True,
            status_code=200,
            url_sanitizada=f"http://{ip_value}/pagina",
            conteudo_html=html,
            erro_codigo=None,
            erro_detalhe_sanitizado=None,
            protocolo_usado="http",
            tipo_autenticacao=config.tipo_autenticacao,
        )


class HtmlPathsDiagnosticTest(TestCase):
    def setUp(self):
        self.previous_key = os.environ.get("PRINTER_CREDENTIALS_SECRET_KEY")
        os.environ["PRINTER_CREDENTIALS_SECRET_KEY"] = Fernet.generate_key().decode("utf-8")

    def tearDown(self):
        if self.previous_key is None:
            os.environ.pop("PRINTER_CREDENTIALS_SECRET_KEY", None)
        else:
            os.environ["PRINTER_CREDENTIALS_SECRET_KEY"] = self.previous_key

    def row(self, **overrides):
        values = {
            "modelo_id": 2,
            "fabricante": "Brother",
            "modelo": "DCP-L1632W",
            "tipo_autenticacao": "basic",
            "usuario": None,
            "senha_criptografada": encrypt_password("senha-ficticia"),
            "caminho_status": "/home/status.html",
            "caminho_informacoes": "/general/information.html?kind=item",
            "caminho_login": None,
            "porta": 80,
            "timeout_segundos": 5,
            "protocolo_preferencial": "auto",
            "validar_ssl": False,
            "maquina_id": 4,
            "maquina": "CAR_PRINT_002",
            "ip": "10.0.0.10",
            "maquina_ativa": True,
            "status_previo": "online",
        }
        values.update(overrides)
        return values

    def target(self, **overrides):
        return select_diagnostic_targets([self.row(**overrides)])[0]

    def test_dry_run_nao_faz_requisicao_http_e_lista_modelo(self):
        fetcher = FakeFetcher()
        target = self.target()

        report = build_report(targets=[target], confirmar=False, fetcher=fetcher)

        self.assertFalse(report["executado"])
        self.assertEqual(report["modo"], "dry_run")
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(report["alvos_planejados"][0]["modelo"], "DCP-L1632W")
        self.assertEqual(report["alvos_planejados"][0]["parser_status"], "disponivel")
        self.assertEqual(
            report["alvos_planejados"][0]["maquina_sanitizada"],
            "MAQUINA_BROTHER_L1632W",
        )
        self.assertTrue(report["alvos_planejados"][0]["ip_configurado"])
        self.assertEqual(report["alvos_planejados"][0]["porta"], 80)
        self.assertNotIn("maquina", report["alvos_planejados"][0])
        self.assertNotIn("ip", report["alvos_planejados"][0])

    def test_selecao_filtra_maquinas_ativas_e_ignora_sem_ip(self):
        rows = [
            self.row(maquina_id=1, ip="10.0.0.1", maquina_ativa=False),
            self.row(maquina_id=2, ip="", maquina_ativa=True),
            self.row(maquina_id=3, ip="10.0.0.3", maquina_ativa=True),
        ]

        target = select_diagnostic_targets(rows)[0]

        self.assertEqual(target.maquina_id, 3)
        self.assertEqual(target.ip, "10.0.0.3")

    def test_selecao_prefere_maquina_online_quando_status_existe(self):
        rows = [
            self.row(maquina_id=1, ip="10.0.0.1", status_previo="desconhecido"),
            self.row(maquina_id=2, ip="10.0.0.2", status_previo="online"),
        ]

        target = select_diagnostic_targets(rows)[0]

        self.assertEqual(target.maquina_id, 2)

    def test_selecao_ignora_offline_por_padrao_e_permite_incluir_offline(self):
        rows = [self.row(maquina_id=1, status_previo="offline")]

        default_target = select_diagnostic_targets(rows)[0]
        included_target = select_diagnostic_targets(rows, incluir_offline=True)[0]

        self.assertEqual(default_target.motivo_ignorado, "html_modelo_sem_maquina_elegivel")
        self.assertEqual(included_target.maquina_id, 1)

    def test_filtros_por_modelo_e_maquina(self):
        rows = [
            self.row(maquina_id=1, modelo="DCP-L1632W"),
            self.row(maquina_id=9, modelo="IR-C3326I", fabricante="Canon", modelo_id=3),
        ]

        by_model = filter_candidate_rows(rows, modelo_filter="Canon IR-C3326I")
        by_machine = filter_candidate_rows(rows, maquina_id=1)

        self.assertEqual(len(by_model), 1)
        self.assertEqual(by_model[0]["fabricante"], "Canon")
        self.assertEqual(len(by_machine), 1)
        self.assertEqual(by_machine[0]["maquina_id"], 1)

    def test_diagnostico_real_exige_confirmar_para_chamar_fetcher(self):
        fetcher = FakeFetcher()
        target = self.target()

        build_report(targets=[target], confirmar=False, fetcher=fetcher)

        self.assertEqual(fetcher.calls, [])

    def test_status_usa_cliente_html_seguro_e_basic(self):
        fetcher = FakeFetcher()

        result = diagnose_status_path(self.target(tipo_autenticacao="basic"), fetcher=fetcher)

        self.assertTrue(result["sucesso"])
        self.assertEqual(fetcher.calls[0]["page_type"], "status")
        self.assertEqual(fetcher.calls[0]["tipo_autenticacao"], "basic")
        self.assertEqual(fetcher.calls[0]["porta"], 80)
        self.assertEqual(result["estado_principal"], "Em espera")
        self.assertEqual(result["maquina_sanitizada"], "MAQUINA_BROTHER_L1632W")
        self.assertTrue(result["ip_configurado"])
        self.assertEqual(result["porta"], 80)

    def test_status_canon_monta_porta_8000(self):
        fetcher = FakeFetcher()
        target = self.target(
            fabricante="Canon",
            modelo="IR-C3326I",
            modelo_id=3,
            caminho_status="/",
            porta=8000,
            protocolo_preferencial="http",
        )

        result = diagnose_status_path(target, fetcher=fetcher)

        self.assertEqual(fetcher.calls[0]["porta"], 8000)
        self.assertEqual(fetcher.calls[0]["protocolo_preferencial"], "http")
        self.assertEqual(result["porta"], 8000)
        self.assertEqual(result["maquina_sanitizada"], "MAQUINA_CANON_IR_C3326I")

    def test_informacoes_usa_cliente_html_seguro_e_digest(self):
        fetcher = FakeFetcher()

        result = diagnose_information_path(
            self.target(tipo_autenticacao="digest"),
            fetcher=fetcher,
        )

        self.assertTrue(result["sucesso"])
        self.assertEqual(fetcher.calls[0]["page_type"], "informacoes")
        self.assertEqual(fetcher.calls[0]["tipo_autenticacao"], "digest")

    def test_form_e_cookie_retornam_erro_controlado(self):
        for auth_type in ("form", "cookie"):
            with self.subTest(auth_type=auth_type):
                fetcher = FakeFetcher()
                target = self.target(tipo_autenticacao=auth_type)

                status_result = diagnose_status_path(target, fetcher=fetcher)
                info_result = diagnose_information_path(target, fetcher=fetcher)

                self.assertEqual(
                    status_result["erro_codigo"],
                    "autenticacao_nao_suportada_nesta_etapa",
                )
                self.assertEqual(
                    info_result["erro_codigo"],
                    "autenticacao_nao_suportada_nesta_etapa",
                )
                self.assertEqual(fetcher.calls, [])

    def test_status_sem_parser_retorna_erro_controlado(self):
        fetcher = FakeFetcher()
        target = self.target(fabricante="HP", modelo="MFP-4305", modelo_id=9)

        result = diagnose_status_path(target, fetcher=fetcher)

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "html_parser_nao_configurado")
        self.assertTrue(result["html_recebido"])

    def test_parser_brother_detecta_estado_no_diagnostico(self):
        fetcher = FakeFetcher([HtmlClientResponse(True, 200, "http://x", status_html("Dormindo"), None, None, "http", "basic")])

        result = diagnose_status_path(self.target(), fetcher=fetcher)

        self.assertTrue(result["sucesso"])
        self.assertEqual(result["estado_principal"], "Dormindo")
        self.assertEqual(result["mensagens_normalizadas"], ["dormindo"])

    def test_caminho_informacoes_detecta_capacidades(self):
        capabilities = detect_information_capabilities(information_html())

        self.assertTrue(capabilities["modelo"])
        self.assertTrue(capabilities["numero_serie"])
        self.assertTrue(capabilities["firmware"])
        self.assertTrue(capabilities["contador_total"])
        self.assertTrue(capabilities["toner"])
        self.assertTrue(capabilities["tambor"])
        self.assertTrue(capabilities["papel"])
        self.assertTrue(capabilities["bandejas"])
        self.assertTrue(capabilities["paginas_por_tamanho"])
        self.assertTrue(capabilities["paginas_por_tipo"])
        self.assertTrue(capabilities["digitalizacoes"])
        self.assertTrue(capabilities["erros"])

    def test_relatorios_json_e_md_nao_contem_html_ou_segredos(self):
        raw_html = "<html><body>Em espera senha-ficticia Authorization Cookie CSRF</body></html>"
        fetcher = FakeFetcher(
            [
                HtmlClientResponse(True, 200, "http://x", raw_html, None, None, "http", "basic"),
                HtmlClientResponse(True, 200, "http://x", information_html(), None, None, "http", "basic"),
            ]
        )
        report = build_report(targets=[self.target()], confirmar=True, fetcher=fetcher)

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, md_path = write_reports(report, output_dir=Path(tmpdir))
            content = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")

        for forbidden in (
            "<html",
            "CAR_PRINT_002",
            "10.0.0.10",
            "senha-ficticia",
            "Authorization",
            "Cookie",
            "CSRF",
            "senha_criptografada",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)
        self.assertIn("estado_principal", content)
        self.assertIn("mensagens_brutas", content)
        self.assertIn("mensagens_normalizadas", content)
        self.assertIn("erro_codigo", content)
        self.assertIn("MAQUINA_BROTHER_L1632W", content)

    def test_markdown_contem_matriz_por_modelo(self):
        report = build_report(targets=[self.target()], confirmar=False)
        markdown = build_markdown(report)

        self.assertIn("| Modelo | Status HTML | Informacoes HTML |", markdown)
        self.assertIn("Brother DCP-L1632W", markdown)

    def test_logs_nao_contem_html_ou_credenciais(self):
        fetcher = FakeFetcher()
        with patch("logging.Logger._log") as log_method:
            result = diagnose_status_path(self.target(), fetcher=fetcher)

        self.assertTrue(result["sucesso"])
        log_method.assert_not_called()

    def test_nenhum_teste_faz_chamada_real_de_rede(self):
        with patch("requests.sessions.Session.request") as request:
            result = diagnose_status_path(self.target(), fetcher=FakeFetcher())

        self.assertTrue(result["sucesso"])
        request.assert_not_called()

    def test_nao_cria_tabela_cascata_ou_task(self):
        files = [
            PROJECT_ROOT
            / "backend/app/modules/printers/monitoring/html_diagnostics/diagnostic.py",
            PROJECT_ROOT / "backend/pyteste/diagnostico_html_modelos.py",
        ]
        content = "\n".join(path.read_text(encoding="utf-8") for path in files)

        self.assertNotIn("tentativas_coleta_impressoras", content)
        self.assertNotIn("sync_machine_alerts_from_collection_result", content)
        self.assertNotIn("collect_and_sync_machine_alerts", content)
        self.assertNotIn("celery_app", content)
        self.assertNotIn("CREATE TABLE", content.upper())

    def test_resultado_confirmado_gera_matriz(self):
        report = build_report(targets=[self.target()], confirmar=True, fetcher=FakeFetcher())
        matrix = build_model_matrix(report["resultados"])

        self.assertEqual(matrix[0]["modelo"], "Brother DCP-L1632W")
        self.assertEqual(matrix[0]["status_html"], "OK")
        self.assertEqual(matrix[0]["informacoes_html"], "OK")
