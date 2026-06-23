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
from backend.app.modules.printers.monitoring.html_diagnostics.dynamic_status import (
    DynamicHttpResult,
    analyze_dynamic_script,
    build_dynamic_status_report,
    classify_dynamic_endpoint,
    diagnose_dynamic_status,
    extract_script_references,
    sanitize_relative_asset_path,
    write_dynamic_status_reports,
)
from backend.app.modules.printers.monitoring.html_diagnostics.public_status import (
    PublicStatusHttpResult,
    build_public_status_report,
    diagnose_public_status_path,
    diagnose_public_status_target,
    write_public_status_reports,
)


PROJECT_ROOT = Path(__file__).resolve().parents[7]
PARSER_FIXTURE_DIR = (
    PROJECT_ROOT / "backend/app/modules/printers/monitoring/html_parsers/tests/fixtures"
)
DIAGNOSTIC_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


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


def parser_fixture_html(name: str) -> str:
    return (PARSER_FIXTURE_DIR / name).read_text(encoding="utf-8")


def diagnostic_fixture_text(name: str) -> str:
    return (DIAGNOSTIC_FIXTURE_DIR / name).read_text(encoding="utf-8")


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
                "session_id": id(session) if session is not None else None,
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


class FakeDynamicFetcher:
    def __init__(self, responses=None):
        self.responses = dict(responses or {})
        self.calls = []

    def __call__(self, target, session, path, *, method="GET", protocol=None, referer_path=None):
        self.calls.append(
            {
                "path": path,
                "method": method,
                "protocol": protocol,
                "referer_path": referer_path,
                "session_id": id(session) if session is not None else None,
            }
        )
        key = (method.upper(), path)
        value = self.responses.get(key, "")
        if isinstance(value, DynamicHttpResult):
            return value
        return DynamicHttpResult(
            sucesso=True,
            status_code=200,
            conteudo=value,
        )


class FakePublicStatusFetcher:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, target, session):
        self.calls.append(
            {
                "path": target.caminho_status,
                "session_id": id(session),
                "session": session,
            }
        )
        return self.response


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

    def test_cookie_retorna_erro_controlado(self):
        fetcher = FakeFetcher()
        target = self.target(tipo_autenticacao="cookie")

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

    def test_form_brother_registra_metadados_login_sem_expor_segredos(self):
        metadata = {
            "login_container_detected": True,
            "login_form_detected": True,
            "login_container_id": "LogInOutBox",
            "password_input_detected": True,
            "password_input_id": "LogBox",
            "csrf_detected": True,
            "hidden_fields_count": 2,
            "post_executado": True,
            "cookies_recebidos": True,
        }
        fetcher = FakeFetcher(
            [
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    parser_fixture_html("brother_dcp_l1632w_status_real_shape.html"),
                    None,
                    None,
                    "http",
                    "form",
                    metadata,
                )
            ]
        )

        result = diagnose_status_path(self.target(tipo_autenticacao="form"), fetcher=fetcher)
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertTrue(result["sucesso"])
        self.assertEqual(result["auth_state"]["autenticado"], True)
        self.assertEqual(result["auth_state"]["tem_moni_data"], True)
        self.assertEqual(result["auth_state"]["tem_status_moni"], True)
        self.assertEqual(result["diagnostico_login"]["login_form_detected"], True)
        self.assertEqual(result["diagnostico_login"]["password_input_detected"], True)
        self.assertEqual(result["diagnostico_login"]["csrf_detected"], True)
        self.assertEqual(result["diagnostico_login"]["hidden_fields_count"], 2)
        self.assertEqual(fetcher.calls[0]["tipo_autenticacao"], "form")
        self.assertNotIn("senha-ficticia", serialized)
        self.assertNotIn("CSRF_SANITIZADO", serialized)
        self.assertNotIn("Cookie:", serialized)

    def test_diagnostico_brother_registra_login_requerido(self):
        fetcher = FakeFetcher(
            [
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    parser_fixture_html("brother_dcp_l1632w_status_login_required.html"),
                    None,
                    None,
                    "http",
                    "basic",
                )
            ]
        )

        result = diagnose_status_path(self.target(), fetcher=fetcher)
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "html_autenticacao_requerida")
        self.assertEqual(result["auth_state"]["login_requerido"], True)
        self.assertEqual(result["auth_state"]["tem_log_in_out_box"], True)
        self.assertEqual(result["auth_state"]["tem_logbox"], True)
        self.assertEqual(result["auth_state"]["tem_csrf"], True)
        self.assertEqual(result["auth_state"]["tem_moni_data"], False)
        self.assertNotIn("CSRF_SANITIZADO", serialized)

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

    def test_diagnostico_de_falha_sanitiza_amostra_visivel(self):
        raw_html = """
        <html>
          <body>
            <p>Status</p>
            <p>CAR_PRINT_002 10.0.0.10 Authorization Cookie CSRF</p>
            <p>Toner Level</p>
          </body>
        </html>
        """
        fetcher = FakeFetcher(
            [HtmlClientResponse(True, 200, "http://x", raw_html, None, None, "http", "basic")]
        )

        result = diagnose_status_path(self.target(), fetcher=fetcher)
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertFalse(result["sucesso"])
        self.assertIn("diagnostico_parser", result)
        self.assertNotIn("<html", serialized.lower())
        self.assertNotIn("CAR_PRINT_002", serialized)
        self.assertNotIn("10.0.0.10", serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("Cookie", serialized)
        self.assertNotIn("CSRF", serialized)

    def test_diagnostico_l1632w_inclui_metadados_status_e_manutencao(self):
        fetcher = FakeFetcher(
            [
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    parser_fixture_html("brother_dcp_l1632w_status_real_shape.html"),
                    None,
                    None,
                    "http",
                    "basic",
                ),
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    parser_fixture_html("brother_dcp_l1632w_maintenance_real_shape.html"),
                    None,
                    None,
                    "http",
                    "basic",
                ),
            ]
        )

        report = build_report(targets=[self.target()], confirmar=True, fetcher=fetcher)
        result = report["resultados"][0]

        self.assertTrue(result["status"]["sucesso"])
        self.assertEqual(result["status"]["estado_principal"], "Em espera")
        self.assertTrue(result["status"]["metadados"]["nivel_toner_bloco_detectado"])
        self.assertEqual(result["status"]["metadados"]["nivel_toner_labels"], ["BK"])
        self.assertFalse(
            result["status"]["metadados"]["nivel_toner_percentual_disponivel"]
        )
        self.assertTrue(result["status"]["moni_data_debug"]["tem_moni_data"])
        self.assertTrue(result["status"]["moni_data_debug"]["tem_moni_class"])
        self.assertEqual(result["status"]["moni_data_debug"]["tags_filhas"], ["span"])
        self.assertEqual(
            result["status"]["status_terms_detected"],
            ["Em espera"],
        )
        self.assertEqual(
            result["status"]["comparacao_shape_moni_data"]["provavel_causa"],
            "moni_data_com_moni_detectado",
        )
        self.assertEqual(
            result["informacoes"]["maintenance_info"],
            {
                "total_paginas_impressas_a4_letter": 4556,
                "unidade_tambor_percentual": 55,
                "toner_percentual": 30,
            },
        )

    def test_diagnostico_l1632w_inclui_estado_manutencao_controlado(self):
        fetcher = FakeFetcher(
            [
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    parser_fixture_html("brother_dcp_l1632w_status_authenticated.html"),
                    None,
                    None,
                    "http",
                    "basic",
                ),
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    parser_fixture_html("brother_dcp_l1632w_maintenance_authenticated.html"),
                    None,
                    None,
                    "http",
                    "basic",
                ),
            ]
        )

        report = build_report(targets=[self.target()], confirmar=True, fetcher=fetcher)
        result = report["resultados"][0]

        self.assertTrue(result["status"]["sucesso"])
        self.assertEqual(result["status"]["auth_state"]["autenticado"], True)
        self.assertEqual(result["status"]["auth_state"]["login_requerido"], False)
        self.assertTrue(result["informacoes"]["maintenance_state"]["tem_dl_items"])
        self.assertTrue(result["informacoes"]["maintenance_state"]["tem_dl_items_info_1line"])
        self.assertTrue(result["informacoes"]["maintenance_debug"]["tem_dl_items"])
        self.assertIn(
            "Contador pag.",
            result["informacoes"]["maintenance_debug"]["labels_detectados"],
        )
        self.assertTrue(
            result["informacoes"]["maintenance_debug"]["campos_extraidos"][
                "contador_paginas"
            ]
        )
        self.assertEqual(result["informacoes"]["maintenance_info"]["contador_paginas"], 4556)
        self.assertEqual(
            result["informacoes"]["maintenance_info"]["total_paginas_impressas_a4_letter"],
            4556,
        )

    def test_diagnostico_l1632w_registra_texto_direto_moni_data(self):
        fetcher = FakeFetcher(
            [
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    parser_fixture_html("brother_dcp_l1632w_status_moni_text_without_class.html"),
                    None,
                    None,
                    "http",
                    "basic",
                )
            ]
        )

        result = diagnose_status_path(self.target(), fetcher=fetcher)
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertTrue(result["sucesso"])
        self.assertEqual(result["estado_principal"], "Em espera")
        self.assertFalse(result["moni_data_debug"]["tem_moni_class"])
        self.assertEqual(
            result["comparacao_shape_moni_data"]["provavel_causa"],
            "moni_data_com_texto_sem_classe_moni",
        )
        self.assertNotIn("<div", serialized)
        self.assertNotIn("Cookie", serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("CSRF", serialized)

    def test_diagnostico_l1632w_registra_moni_data_vazio(self):
        fetcher = FakeFetcher(
            [
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    parser_fixture_html("brother_dcp_l1632w_status_moni_empty.html"),
                    None,
                    None,
                    "http",
                    "basic",
                )
            ]
        )

        result = diagnose_status_path(self.target(), fetcher=fetcher)

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "html_sessao_brother_invalida")
        self.assertEqual(result["moni_data_debug"]["tags_filhas"], [])
        self.assertTrue(result["moni_data_debug"]["parece_vazio"])
        self.assertEqual(
            result["comparacao_shape_moni_data"]["provavel_causa"],
            "moni_data_vazio",
        )

    def test_diagnostico_dinamico_lista_scripts_relativos(self):
        scripts = extract_script_references(
            diagnostic_fixture_text("brother_l1632w_status_page_with_scripts.html")
        )

        self.assertEqual(scripts["scripts_detectados"], ["/common/js/lcddisplay.js"])
        self.assertEqual(scripts["scripts_inline"], ["inline_status_1"])
        self.assertNotIn("<script", json.dumps(scripts, ensure_ascii=False))

    def test_diagnostico_dinamico_sanitiza_url_absoluta_com_ip(self):
        path = sanitize_relative_asset_path("http://192.0.2.10/common/js/lcddisplay.js")

        self.assertEqual(path, "/common/js/lcddisplay.js")

    def test_analisador_js_detecta_termos_e_endpoint_candidato(self):
        analysis = analyze_dynamic_script(
            diagnostic_fixture_text("brother_l1632w_lcddisplay_candidate.js"),
            script_path="/common/js/lcddisplay.js",
        )
        serialized = json.dumps(analysis, ensure_ascii=False)

        self.assertIn("refreshLCD", analysis["termos_encontrados"])
        self.assertIn("judge_refresh", analyze_dynamic_script("judge_refresh(60000);", script_path="inline_status_1")["termos_encontrados"])
        self.assertIn("XMLHttpRequest", analysis["termos_encontrados"])
        self.assertIn("/home/status.html", analysis["endpoints_candidatos"])
        self.assertIn("POST", analysis["metodos_candidatos"])
        self.assertIn("pageid", analysis["parametros_candidatos"])
        self.assertIn("Refresh", analysis["parametros_candidatos"])
        self.assertNotIn("xhr.open", serialized)

    def test_diagnostico_dinamico_ignora_endpoint_administrativo(self):
        allowed, reason = classify_dynamic_endpoint("/admin/config.html")

        self.assertFalse(allowed)
        self.assertEqual(reason, "endpoint administrativo fora do escopo")

    def test_diagnostico_dinamico_confirma_resposta_com_em_espera(self):
        status_fetcher = FakeFetcher(
            [
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    diagnostic_fixture_text("brother_l1632w_status_page_with_scripts.html"),
                    None,
                    None,
                    "http",
                    "form",
                    {"cookies_recebidos": True, "csrf_detected": True},
                )
            ]
        )
        dynamic_fetcher = FakeDynamicFetcher(
            {
                ("GET", "/common/js/lcddisplay.js"): diagnostic_fixture_text(
                    "brother_l1632w_lcddisplay_candidate.js"
                ),
                ("POST", "/home/status.html"): diagnostic_fixture_text(
                    "brother_l1632w_dynamic_status_response.html"
                ),
            }
        )

        result = diagnose_dynamic_status(
            self.target(tipo_autenticacao="form"),
            status_fetcher=status_fetcher,
            resource_fetcher=dynamic_fetcher,
        )
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertTrue(result["texto_operacional_encontrado"])
        self.assertEqual(result["mensagem_operacional_encontrada"], "Em espera")
        self.assertEqual(
            result["endpoint_dinamico_confirmado"]["endpoint"],
            "/home/status.html",
        )
        self.assertEqual(dynamic_fetcher.calls[0]["session_id"], status_fetcher.calls[0]["session_id"])
        self.assertNotIn("<html", serialized.lower())
        self.assertNotIn("Cookie", serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("CSRFToken", serialized)
        self.assertNotIn("senha-ficticia", serialized)

    def test_diagnostico_dinamico_registra_resposta_vazia_controlada(self):
        status_fetcher = FakeFetcher(
            [
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    diagnostic_fixture_text("brother_l1632w_status_page_with_scripts.html"),
                    None,
                    None,
                    "http",
                    "form",
                    {"cookies_recebidos": True},
                )
            ]
        )
        dynamic_fetcher = FakeDynamicFetcher(
            {
                ("GET", "/common/js/lcddisplay.js"): diagnostic_fixture_text(
                    "brother_l1632w_lcddisplay_candidate.js"
                ),
                ("POST", "/home/status.html"): diagnostic_fixture_text(
                    "brother_l1632w_dynamic_status_response_empty.html"
                ),
            }
        )

        result = diagnose_dynamic_status(
            self.target(tipo_autenticacao="form"),
            status_fetcher=status_fetcher,
            resource_fetcher=dynamic_fetcher,
        )

        self.assertFalse(result["texto_operacional_encontrado"])
        self.assertEqual(result["causa_sanitizada"], "endpoint_candidato_sem_texto_operacional")
        self.assertEqual(result["chamadas_candidatas_executadas"][0]["mensagens_detectadas"], [])

    def test_diagnostico_dinamico_registra_causa_sem_endpoint(self):
        status_fetcher = FakeFetcher(
            [
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    "<html><body><script>judge_refresh(60000);</script></body></html>",
                    None,
                    None,
                    "http",
                    "form",
                )
            ]
        )

        report = build_dynamic_status_report(
            targets=[self.target(tipo_autenticacao="form")],
            confirmar=True,
            status_fetcher=status_fetcher,
            resource_fetcher=FakeDynamicFetcher(),
        )
        result = report["resultados"][0]

        self.assertEqual(result["causa_sanitizada"], "scripts_sem_endpoint_candidato")
        self.assertEqual(result["endpoints_candidatos"], [])

    def test_relatorio_dinamico_nao_contem_html_js_ou_segredos(self):
        status_fetcher = FakeFetcher(
            [
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    diagnostic_fixture_text("brother_l1632w_status_page_with_scripts.html"),
                    None,
                    None,
                    "http",
                    "form",
                    {"cookies_recebidos": True, "csrf_detected": True},
                )
            ]
        )
        dynamic_fetcher = FakeDynamicFetcher(
            {
                ("GET", "/common/js/lcddisplay.js"): diagnostic_fixture_text(
                    "brother_l1632w_lcddisplay_candidate.js"
                ),
                ("POST", "/home/status.html"): diagnostic_fixture_text(
                    "brother_l1632w_dynamic_status_response.html"
                ),
            }
        )
        report = build_dynamic_status_report(
            targets=[self.target(tipo_autenticacao="form")],
            confirmar=True,
            status_fetcher=status_fetcher,
            resource_fetcher=dynamic_fetcher,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, md_path = write_dynamic_status_reports(
                report,
                output_dir=Path(tmpdir),
            )
            content = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")

        for forbidden in (
            "<html",
            "<script",
            "xhr.open",
            "CAR_PRINT_002",
            "192.0.2.10",
            "senha-ficticia",
            "Authorization",
            "Cookie",
            "CSRFToken",
            "senha_criptografada",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)

    def test_diagnostico_dinamico_nao_acessa_rede_em_teste(self):
        with patch("requests.sessions.Session.request") as request:
            report = build_dynamic_status_report(
                targets=[self.target(tipo_autenticacao="form")],
                confirmar=True,
                status_fetcher=FakeFetcher(
                    [
                        HtmlClientResponse(
                            True,
                            200,
                            "http://x",
                            "<html><body></body></html>",
                            None,
                            None,
                            "http",
                            "form",
                        )
                    ]
                ),
                resource_fetcher=FakeDynamicFetcher(),
            )

        self.assertTrue(report["executado"])
        request.assert_not_called()

    def test_status_publico_brother_l1632w_usa_sessao_sem_autenticacao(self):
        public_fetcher = FakePublicStatusFetcher(
            PublicStatusHttpResult(
                sucesso=True,
                status_code=200,
                conteudo=diagnostic_fixture_text(
                    "brother_dcp_l1632w_public_status_with_text.html"
                ),
                protocolo_usado="http",
            )
        )
        maintenance_fetcher = FakeFetcher(
            [
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    parser_fixture_html("brother_dcp_l1632w_maintenance_authenticated.html"),
                    None,
                    None,
                    "http",
                    "form",
                    {"post_executado": True, "csrf_detected": True},
                )
            ]
        )

        result = diagnose_public_status_target(
            self.target(tipo_autenticacao="form"),
            public_fetcher=public_fetcher,
            maintenance_fetcher=maintenance_fetcher,
        )
        status_result = result["status_publico"]
        maintenance_result = result["manutencao"]

        self.assertTrue(status_result["sucesso"])
        self.assertEqual(status_result["estado_principal"], "Em espera")
        self.assertEqual(status_result["origem"], "html_publico")
        self.assertFalse(status_result["autenticacao_usada"])
        self.assertFalse(status_result["login_executado"])
        self.assertFalse(status_result["post_executado"])
        self.assertFalse(status_result["cookie_autenticado_usado"])
        self.assertEqual(public_fetcher.calls[0]["path"], "/home/status.html")
        self.assertEqual(maintenance_fetcher.calls[0]["page_type"], "informacoes")
        self.assertTrue(maintenance_result["autenticacao_usada"])
        self.assertTrue(maintenance_result["login_executado"])
        self.assertEqual(maintenance_result["maintenance_info"]["contador_paginas"], 4556)
        self.assertNotEqual(
            public_fetcher.calls[0]["session_id"],
            maintenance_fetcher.calls[0]["session_id"],
        )
        self.assertEqual(result["decisao_final"]["status"], "resolvida")

    def test_status_publico_brother_l1632w_moni_data_vazio_e_controlado(self):
        public_fetcher = FakePublicStatusFetcher(
            PublicStatusHttpResult(
                sucesso=True,
                status_code=200,
                conteudo=diagnostic_fixture_text(
                    "brother_dcp_l1632w_public_status_empty.html"
                ),
                protocolo_usado="http",
            )
        )

        result = diagnose_public_status_path(
            self.target(tipo_autenticacao="form"),
            public_fetcher=public_fetcher,
        )

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "html_status_publico_vazio")
        self.assertEqual(result["causa_sanitizada"], "moni_data_vazio_sem_login")
        self.assertFalse(result["autenticacao_usada"])
        self.assertFalse(result["login_executado"])
        self.assertFalse(result["post_executado"])

    def test_status_publico_brother_l1632w_sem_moni_data_e_controlado(self):
        public_fetcher = FakePublicStatusFetcher(
            PublicStatusHttpResult(
                sucesso=True,
                status_code=200,
                conteudo="<html><body>Status indisponivel</body></html>",
                protocolo_usado="http",
            )
        )

        result = diagnose_public_status_path(
            self.target(tipo_autenticacao="form"),
            public_fetcher=public_fetcher,
        )

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "html_status_publico_nao_detectado")
        self.assertEqual(result["causa_sanitizada"], "moni_data_ausente_sem_login")

    def test_relatorio_status_publico_nao_contem_html_ips_ou_segredos(self):
        public_fetcher = FakePublicStatusFetcher(
            PublicStatusHttpResult(
                sucesso=True,
                status_code=200,
                conteudo=(
                    "<html><body><div id='moni_data'>Em espera "
                    "senha-ficticia Authorization Cookie CSRFToken "
                    "10.0.0.10 CAR_PRINT_002</div></body></html>"
                ),
                protocolo_usado="http",
            )
        )
        maintenance_fetcher = FakeFetcher(
            [
                HtmlClientResponse(
                    True,
                    200,
                    "http://x",
                    parser_fixture_html("brother_dcp_l1632w_maintenance_authenticated.html"),
                    None,
                    None,
                    "http",
                    "form",
                    {"post_executado": True, "csrf_detected": True},
                )
            ]
        )
        report = build_public_status_report(
            targets=[self.target(tipo_autenticacao="form")],
            confirmar=True,
            public_fetcher=public_fetcher,
            maintenance_fetcher=maintenance_fetcher,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, md_path = write_public_status_reports(
                report,
                output_dir=Path(tmpdir),
            )
            content = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")

        for forbidden in (
            "<html",
            "CAR_PRINT_002",
            "10.0.0.10",
            "senha-ficticia",
            "Authorization",
            "Cookie",
            "CSRFToken",
            "senha_criptografada",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)
        self.assertIn("html_publico", content)
        self.assertIn("MAQUINA_BROTHER_L1632W", content)

    def test_diagnostico_status_publico_nao_acessa_rede_em_teste(self):
        with patch("requests.sessions.Session.request") as request:
            report = build_public_status_report(
                targets=[self.target(tipo_autenticacao="form")],
                confirmar=True,
                public_fetcher=FakePublicStatusFetcher(
                    PublicStatusHttpResult(
                        sucesso=True,
                        status_code=200,
                        conteudo=diagnostic_fixture_text(
                            "brother_dcp_l1632w_public_status_with_text.html"
                        ),
                        protocolo_usado="http",
                    )
                ),
                maintenance_fetcher=FakeFetcher(
                    [
                        HtmlClientResponse(
                            True,
                            200,
                            "http://x",
                            parser_fixture_html(
                                "brother_dcp_l1632w_maintenance_authenticated.html"
                            ),
                            None,
                            None,
                            "http",
                            "form",
                        )
                    ]
                ),
            )

        self.assertTrue(report["executado"])
        request.assert_not_called()

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
            PROJECT_ROOT
            / "backend/app/modules/printers/monitoring/html_diagnostics/public_status.py",
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
