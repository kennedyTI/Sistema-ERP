from dataclasses import asdict
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from backend.app.modules.printers.monitoring.html_client.models import HtmlClientResponse
from backend.app.modules.printers.monitoring.html_parsers.brother import (
    BrotherDcpL1632wStatusParser,
    BrotherDcpL2540dwStatusParser,
    build_brother_l1632w_moni_data_debug,
    classify_brother_html_auth_state,
    compare_brother_l1632w_moni_shape,
    detect_brother_l1632w_maintenance_markers,
    detect_brother_l1632w_status_terms,
    extract_brother_moni_status_messages,
    extract_visible_text_chunks,
    parse_brother_dcp_l1632w_maintenance_info,
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
        self.assertEqual(result.mensagens_brutas, ["Ocorreu um erro."])
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

    def test_parser_brother_l1632w_detecta_estado_em_formato_real(self):
        result = parse_status_html_for_model(
            DummyModel(),
            fixture_html("brother_dcp_l1632w_status_real_shape.html"),
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Em espera"])
        self.assertEqual(result.mensagens_normalizadas, ["em espera"])
        self.assertEqual(result.estado_principal, "Em espera")

    def test_parser_brother_l1632w_detecta_estado_autenticado_com_logout(self):
        result = parse_status_html_for_model(
            DummyModel(),
            fixture_html("brother_dcp_l1632w_status_authenticated.html"),
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Em espera"])
        self.assertEqual(result.metadados["auth_state"]["autenticado"], True)
        self.assertEqual(result.metadados["auth_state"]["login_requerido"], False)
        self.assertEqual(result.metadados["auth_state"]["tem_log_in_out_box"], True)
        self.assertEqual(result.metadados["auth_state"]["tem_logbox"], False)
        self.assertEqual(result.metadados["auth_state"]["tem_csrf"], True)
        self.assertEqual(result.metadados["auth_state"]["tem_moni_data"], True)
        self.assertEqual(result.metadados["auth_state"]["tem_status_moni"], True)

    def test_parser_brother_l1632w_detecta_login_requerido(self):
        result = parse_status_html_for_model(
            DummyModel(),
            fixture_html("brother_dcp_l1632w_status_login_required.html"),
        )

        self.assertFalse(result.sucesso)
        self.assertEqual(result.erro_codigo, "html_autenticacao_requerida")
        self.assertEqual(result.metadados["auth_state"]["autenticado"], False)
        self.assertEqual(result.metadados["auth_state"]["login_requerido"], True)
        self.assertEqual(result.metadados["auth_state"]["tem_log_in_out_box"], True)
        self.assertEqual(result.metadados["auth_state"]["tem_logbox"], True)
        self.assertEqual(result.metadados["auth_state"]["tem_csrf"], True)
        self.assertEqual(result.metadados["auth_state"]["tem_moni_data"], False)
        self.assertEqual(result.metadados["auth_state"]["tem_status_moni"], False)
        self.assertNotIn("CSRF_SANITIZADO", str(result))

    def test_classificador_brother_diferencia_autenticado_login_e_parcial(self):
        authenticated = classify_brother_html_auth_state(
            fixture_html("brother_dcp_l1632w_status_authenticated.html")
        )
        login_required = classify_brother_html_auth_state(
            fixture_html("brother_dcp_l1632w_status_login_required.html")
        )
        partial = classify_brother_html_auth_state(
            '<div id="LogInOutBox"><form></form></div>'
        )

        self.assertTrue(authenticated["autenticado"])
        self.assertFalse(authenticated["login_requerido"])
        self.assertIsNone(authenticated["erro_codigo"])
        self.assertFalse(login_required["autenticado"])
        self.assertTrue(login_required["login_requerido"])
        self.assertEqual(login_required["erro_codigo"], "html_autenticacao_requerida")
        self.assertEqual(partial["erro_codigo"], "html_sessao_brother_invalida")

    def test_parser_brother_l1632w_aceita_classe_moni_nao_ok(self):
        html = """
        <div id="moni_data">
          <span class="moni moniWarning">Toner baixo</span>
        </div>
        """

        messages = extract_brother_moni_status_messages(html)
        result = parse_status_html_for_model(DummyModel(), html)

        self.assertEqual(messages, ["Toner baixo"])
        self.assertTrue(result.sucesso)
        self.assertEqual(result.estado_principal, "Toner baixo")

    def test_parser_brother_l1632w_extrai_estado_de_span_moni(self):
        result = parse_status_html_for_model(
            DummyModel(),
            fixture_html("brother_dcp_l1632w_status_moni_span.html"),
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Em espera"])
        self.assertEqual(result.estado_principal, "Em espera")

    def test_parser_brother_l1632w_extrai_estado_de_div_moni(self):
        result = parse_status_html_for_model(
            DummyModel(),
            fixture_html("brother_dcp_l1632w_status_moni_div.html"),
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Toner baixo"])
        self.assertEqual(result.estado_principal, "Toner baixo")

    def test_parser_brother_l1632w_aceita_classes_moni_variadas(self):
        for class_name, expected in (
            ("moniOk", "Em espera"),
            ("moniWarning", "Toner baixo"),
            ("moniError", "Erro"),
            ("moni", "Pronto"),
        ):
            with self.subTest(class_name=class_name):
                html = f'<div id="moni_data"><p class="{class_name}">{expected}</p></div>'
                result = parse_status_html_for_model(DummyModel(), html)

                self.assertTrue(result.sucesso)
                self.assertEqual(result.estado_principal, expected)

    def test_parser_brother_l1632w_usa_texto_direto_do_moni_data(self):
        result = parse_status_html_for_model(
            DummyModel(),
            fixture_html("brother_dcp_l1632w_status_moni_text_without_class.html"),
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Em espera"])
        self.assertEqual(result.metadados["auth_state"]["tem_status_moni"], False)
        self.assertEqual(result.metadados["auth_state"]["tem_moni_class"], False)

    def test_parser_brother_l1632w_moni_data_vazio_retorna_sessao_invalida(self):
        result = parse_status_html_for_model(
            DummyModel(),
            fixture_html("brother_dcp_l1632w_status_moni_empty.html"),
        )

        self.assertFalse(result.sucesso)
        self.assertEqual(result.erro_codigo, "html_sessao_brother_invalida")

    def test_parser_brother_l1632w_usa_dt_estado_como_fallback_final(self):
        html = """
        <dl class="items">
          <dt>Estado do dispositivo</dt>
          <dd>Pronto</dd>
        </dl>
        """

        result = parse_status_html_for_model(DummyModel(), html)

        self.assertTrue(result.sucesso)
        self.assertEqual(result.estado_principal, "Pronto")

    def test_debug_moni_data_sanitizado_lista_shape_sem_html_bruto(self):
        html = """
        <div id="moni_data">
          <span class="moni moniOk">Em espera</span>
        </div>
        """

        debug = build_brother_l1632w_moni_data_debug(html)
        serialized = str(debug)

        self.assertTrue(debug["tem_moni_data"])
        self.assertTrue(debug["tem_moni_class"])
        self.assertTrue(debug["tem_span"])
        self.assertEqual(debug["tags_filhas"], ["span"])
        self.assertEqual(debug["classes_filhas"], ["moni", "moniOk"])
        self.assertEqual(debug["texto_visivel_preview"], "Em espera")
        self.assertNotIn("<span", serialized)

    def test_debug_moni_data_limita_preview_e_oculta_segredos(self):
        html = f"""
        <div id="moni_data">
          senha Cookie Authorization CSRF 10.0.0.10 {"Em espera " * 80}
        </div>
        """

        debug = build_brother_l1632w_moni_data_debug(html)

        self.assertLessEqual(len(debug["texto_visivel_preview"]), 200)
        self.assertNotIn("senha", debug["texto_visivel_preview"].lower())
        self.assertNotIn("Cookie", debug["texto_visivel_preview"])
        self.assertNotIn("Authorization", debug["texto_visivel_preview"])
        self.assertNotIn("CSRF", debug["texto_visivel_preview"])
        self.assertNotIn("10.0.0.10", debug["texto_visivel_preview"])

    def test_comparacao_moni_data_registra_causas_sanitizadas(self):
        detected = compare_brother_l1632w_moni_shape(
            fixture_html("brother_dcp_l1632w_status_moni_span.html")
        )
        direct = compare_brother_l1632w_moni_shape(
            fixture_html("brother_dcp_l1632w_status_moni_text_without_class.html")
        )
        empty = compare_brother_l1632w_moni_shape(
            fixture_html("brother_dcp_l1632w_status_moni_empty.html")
        )

        self.assertEqual(detected["provavel_causa"], "moni_data_com_moni_detectado")
        self.assertEqual(direct["provavel_causa"], "moni_data_com_texto_sem_classe_moni")
        self.assertEqual(empty["provavel_causa"], "moni_data_vazio")

    def test_termos_operacionais_sao_detectados_sem_html_bruto(self):
        terms = detect_brother_l1632w_status_terms(
            fixture_html("brother_dcp_l1632w_status_moni_div.html")
        )

        self.assertEqual(terms, ["Toner baixo"])

    def test_parser_brother_l1632w_detecta_bloco_toner_sem_percentual(self):
        result = parse_status_html_for_model(
            DummyModel(),
            fixture_html("brother_dcp_l1632w_status_real_shape.html"),
        )

        self.assertTrue(result.sucesso)
        self.assertTrue(result.metadados["nivel_toner_bloco_detectado"])
        self.assertEqual(result.metadados["nivel_toner_labels"], ["BK"])
        self.assertFalse(result.metadados["nivel_toner_percentual_disponivel"])
        self.assertNotIn("16", result.mensagens_brutas)

    def test_parser_brother_l1632w_manutencao_extrai_campos_controlados(self):
        info = parse_brother_dcp_l1632w_maintenance_info(
            fixture_html("brother_dcp_l1632w_maintenance_real_shape.html")
        )

        self.assertEqual(info["total_paginas_impressas_a4_letter"], 4556)
        self.assertEqual(info["unidade_tambor_percentual"], 55)
        self.assertEqual(info["toner_percentual"], 30)

    def test_parser_brother_l1632w_manutencao_extrai_contador_paginas(self):
        html = fixture_html("brother_dcp_l1632w_maintenance_authenticated.html")
        info = parse_brother_dcp_l1632w_maintenance_info(html)
        markers = detect_brother_l1632w_maintenance_markers(html)

        self.assertEqual(info["contador_paginas"], 4556)
        self.assertEqual(info["total_paginas_impressas_a4_letter"], 4556)
        self.assertEqual(info["unidade_tambor_percentual"], 55)
        self.assertEqual(info["toner_percentual"], 30)
        self.assertTrue(markers["tem_dl_items"])
        self.assertTrue(markers["tem_dl_items_info_1line"])
        self.assertTrue(markers["tem_contador_paginas"])
        self.assertTrue(markers["tem_a4_letter"])

    def test_parser_brother_l1632w_manutencao_ignora_campos_cadastrais(self):
        html = """
        <html>
          <body>
            <h3>Vida Ãºtil restante</h3>
            <dl class="items">
              <dt>Unidade de tambor*</dt><dd>55%</dd>
              <dt>Toner**</dt><dd>30%</dd>
            </dl>
            <h3>Identificacao</h3>
            <dl class="items">
              <dt>N. de serie</dt><dd>SERIAL-REAL</dd>
              <dt>Versao de firmware principal</dt><dd>1.2.3</dd>
              <dt>Localizacao do dispositivo</dt><dd>LOCAL-REAL</dd>
              <dt>Historico de erros</dt><dd>ERRO-ANTIGO</dd>
            </dl>
          </body>
        </html>
        """

        info = parse_brother_dcp_l1632w_maintenance_info(html)
        serialized = str(info)

        self.assertEqual(info["unidade_tambor_percentual"], 55)
        self.assertEqual(info["toner_percentual"], 30)
        self.assertNotIn("SERIAL-REAL", serialized)
        self.assertNotIn("1.2.3", serialized)
        self.assertNotIn("LOCAL-REAL", serialized)
        self.assertNotIn("ERRO-ANTIGO", serialized)

    def test_parser_brother_l2540dw_mantem_trocar_cilindro(self):
        html = """
        <html>
          <body>
            <dl>
              <dt>Device Status</dt>
              <dd>Trocar</dd>
              <dd>Cilindro</dd>
            </dl>
          </body>
        </html>
        """

        result = parse_status_html_for_model(DummyModel("Brother", "DCP-L2540DW"), html)

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Trocar Cilindro"])
        self.assertEqual(result.estado_principal, "Trocar Cilindro")

    def test_parser_retorna_multiplas_mensagens_quando_existirem(self):
        html = "<html><body><p>Toner baixo</p><p>Tampa aberta</p></body></html>"

        result = parse_status_html_for_model(DummyModel(), html)

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Toner baixo", "Tampa aberta"])
        self.assertEqual(result.mensagens_normalizadas, ["toner baixo", "tampa aberta"])

    def test_parser_canon_detecta_formato_real_com_mensagens_quebradas(self):
        result = parse_status_html_for_model(
            DummyModel("Canon", "IR-C3326I"),
            fixture_html("canon_ir_c3326i_status_real_shape.html"),
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(result.estado_principal, "Poderá ter ocorrido um erro.")
        self.assertNotIn("Ocorreu um erro.", result.mensagens_brutas)
        self.assertIn("o toner magenta esta baixo.", result.mensagens_normalizadas)
        self.assertIn("o toner amarelo esta baixo.", result.mensagens_normalizadas)
        self.assertNotIn("Modo de espera.", result.mensagens_brutas)

    def test_parser_canon_prioriza_informacoes_de_erro(self):
        html = fixture_html("canon_ir_c3326i_status_with_error_info.html")

        result = parse_status_html_for_model(DummyModel("Canon", "IR-C3326I"), html)

        self.assertTrue(result.sucesso)
        self.assertEqual(
            result.mensagens_brutas,
            [
                "Poderá ter ocorrido um erro.",
                "O toner Magenta está baixo.",
                "O toner Amarelo está baixo.",
            ],
        )
        self.assertEqual(result.estado_principal, "Poderá ter ocorrido um erro.")
        self.assertNotIn("Ocorreu um erro.", result.mensagens_brutas)

    def test_parser_canon_detecta_modo_espera_da_impressora(self):
        html = """
        <html>
          <body>
            <h1>Estado do dispositivo</h1>
            <section>
              <h2>Impressora</h2>
              <p>Impressora</p>
              <p>Modo de espera</p>
            </section>
          </body>
        </html>
        """

        result = parse_status_html_for_model(DummyModel("Canon", "IR-C3326I"), html)

        self.assertTrue(result.sucesso)
        self.assertEqual(result.estado_principal, "Modo de espera")
        self.assertEqual(result.mensagens_brutas, ["Modo de espera"])

    def test_parser_canon_usa_estado_da_impressora_quando_erro_vazio(self):
        html = """
        <html>
          <body>
            <h1>Estado do dispositivo</h1>
            <dl>
              <dt>Impressora :</dt>
              <dd>Modo de espera.</dd>
              <dt>Scanner :</dt>
              <dd>Modo de espera.</dd>
            </dl>
            <h2>Informações de Erro</h2>
            <p>Nenhum</p>
            <h2>Informações de Consumíveis</h2>
          </body>
        </html>
        """

        result = parse_status_html_for_model(DummyModel("Canon", "IR-C3326I"), html)

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Modo de espera."])

    def test_parser_samsung_detecta_estado_e_alerta_separados(self):
        result = parse_status_html_for_model(
            DummyModel("Samsung", "K4250LX"),
            fixture_html("samsung_k4350_status_real_shape.html"),
        )

        self.assertTrue(result.sucesso)
        self.assertEqual(result.mensagens_brutas, ["Erro", "1 Alerta(s) ocorridos"])
        self.assertEqual(result.estado_principal, "Erro")

    def test_parser_hp_detecta_formato_real_e_prioriza_aviso(self):
        result = parse_status_html_for_model(
            DummyModel("HP", "MFP-4303"),
            fixture_html("hp_mfp_4303_status_real_shape.html"),
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
        self.assertEqual(result.erro_codigo, "html_status_nao_detectado")
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
            "senha-ficticia",
            "senha_criptografada",
            "cookie",
            "authorization",
            "grupo" + "si" + "mec",
            "si" + "mec",
            "10.",
            "192.168.",
            "http://",
            "https://",
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
