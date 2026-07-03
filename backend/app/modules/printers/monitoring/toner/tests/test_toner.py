from unittest import TestCase
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.celery_app import celery_app
from backend.app.modules.printers.machines.models import PrinterMachine, PrinterModel
from backend.app.modules.printers.monitoring.config import MonitoringSettings
from backend.app.modules.printers.monitoring.html_client.models import (
    HtmlAccessConfig,
    HtmlClientResponse,
)
from backend.app.modules.printers.monitoring.snmp.models import PrinterSnmpOid
from backend.app.modules.printers.monitoring.tasks import printers_toner_all
from backend.app.modules.printers.monitoring.toner.collector import (
    PRT_MARKER_SUPPLIES_DESCRIPTION_OID,
    PRT_MARKER_SUPPLIES_LEVEL_OID,
    PRT_MARKER_SUPPLIES_MAX_CAPACITY_OID,
    PRT_MARKER_SUPPLIES_SUPPLY_UNIT_OID,
    PRT_MARKER_SUPPLIES_TYPE_OID,
    calculate_toner_percentage,
    collect_toner_items_from_printer_mib,
    is_toner_supply,
    resolve_toner_color,
    toner_items_from_mib_rows,
)
from backend.app.modules.printers.monitoring.toner.models import (
    HistoricoTonerImpressora,
    StatusTonerImpressora,
)
from backend.app.modules.printers.monitoring.toner.fallbacks import (
    BROTHER_TONER_BAR_MAX_HEIGHT,
    WEB_STATUS_PATHS,
    brother_toner_percentage,
    collect_toner_from_snmp_oids,
    collect_toner_from_web_status,
    has_valid_toner_percentage,
    parse_brother_tonerremain,
)
from backend.app.modules.printers.monitoring.toner.services import (
    CANON_IR_C3326I_SNMP_VERSIONS,
    collect_and_sync_machine_toner,
    collect_toner_with_fallbacks,
    run_toner_batch,
    sync_toner_items,
)
from backend.app.modules.printers.status.models import StatusImpressora


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        self.ttls[key] = ex
        return True

    def eval(self, _script, _key_count, key, token):
        if self.values.get(key) != token:
            return 0
        del self.values[key]
        self.ttls.pop(key, None)
        return 1

    def ping(self):
        return True


def supply_walk_result(supplies):
    rows_by_base = {
        PRT_MARKER_SUPPLIES_DESCRIPTION_OID: [],
        PRT_MARKER_SUPPLIES_TYPE_OID: [],
        PRT_MARKER_SUPPLIES_SUPPLY_UNIT_OID: [],
        PRT_MARKER_SUPPLIES_MAX_CAPACITY_OID: [],
        PRT_MARKER_SUPPLIES_LEVEL_OID: [],
    }
    for index, row in enumerate(supplies, start=1):
        suffix = f"1.{index}"
        rows_by_base[PRT_MARKER_SUPPLIES_DESCRIPTION_OID].append(
            {"oid": f"{PRT_MARKER_SUPPLIES_DESCRIPTION_OID}.{suffix}", "value": row["description"]}
        )
        rows_by_base[PRT_MARKER_SUPPLIES_TYPE_OID].append(
            {"oid": f"{PRT_MARKER_SUPPLIES_TYPE_OID}.{suffix}", "value": row.get("type", "3")}
        )
        rows_by_base[PRT_MARKER_SUPPLIES_SUPPLY_UNIT_OID].append(
            {"oid": f"{PRT_MARKER_SUPPLIES_SUPPLY_UNIT_OID}.{suffix}", "value": row.get("unit", "19")}
        )
        rows_by_base[PRT_MARKER_SUPPLIES_MAX_CAPACITY_OID].append(
            {"oid": f"{PRT_MARKER_SUPPLIES_MAX_CAPACITY_OID}.{suffix}", "value": row.get("max", "100")}
        )
        rows_by_base[PRT_MARKER_SUPPLIES_LEVEL_OID].append(
            {"oid": f"{PRT_MARKER_SUPPLIES_LEVEL_OID}.{suffix}", "value": row.get("level")}
        )
    return rows_by_base


class TonerCollectorTest(TestCase):
    def test_cruza_walks_por_indice_e_calcula_percentual(self):
        rows = {
            "1.1": {
                "description": "Black Toner",
                "type": "3",
                "unit": "19",
                "max_capacity": "2000",
                "level": "1000",
            }
        }

        result = toner_items_from_mib_rows(rows)

        self.assertEqual(result[0]["cor"], "black")
        self.assertEqual(result[0]["percentual"], 50)
        self.assertEqual(result[0]["indice_suprimento"], "1.1")

    def test_identifica_toner_por_tipo_snmp(self):
        self.assertTrue(is_toner_supply("Cartucho Preto", "3"))

    def test_identifica_toner_por_descricao(self):
        self.assertTrue(is_toner_supply("Toner Preto", "1"))

    def test_ignora_drum_cilindro_waste_e_papel(self):
        for description in ("Black Drum", "Cilindro preto", "Waste toner", "Paper tray"):
            self.assertFalse(is_toner_supply(description, "3"))

    def test_resolve_cores_principais(self):
        cases = {
            "Black Toner": "black",
            "Toner preto": "black",
            "Cyan Toner": "cyan",
            "Toner ciano": "cyan",
            "Toner azul": "cyan",
            "Magenta Toner": "magenta",
            "Toner vermelho": "magenta",
            "Yellow Toner": "yellow",
            "Toner amarelo": "yellow",
        }
        for description, expected in cases.items():
            self.assertEqual(resolve_toner_color(description), expected)

    def test_unknown_nao_vira_zero(self):
        self.assertIsNone(calculate_toner_percentage("-2", "100"))
        self.assertIsNone(calculate_toner_percentage("150", "-2"))
        self.assertIsNone(calculate_toner_percentage("150", "0"))

    def test_nivel_percentual_da_v1_funciona_com_capacidade_desconhecida(self):
        self.assertEqual(calculate_toner_percentage("37", "-2"), 37)

    def test_nivel_percentual_nao_depende_de_capacidade_valida(self):
        self.assertEqual(calculate_toner_percentage("10", "abc"), 10)

    def test_nivel_maior_que_capacidade_e_limitado(self):
        self.assertEqual(calculate_toner_percentage("150", "100"), 100)

    def test_ordem_v1_retorna_percentual_sem_tentar_v2c(self):
        versions = []
        rows = supply_walk_result(
            [{"description": "Black Toner", "level": "64", "max": "100"}]
        )

        def walker(**kwargs):
            versions.append(kwargs["snmp_version"])
            return {"sucesso": True, "linhas": rows[kwargs["base_oid"]]}

        result = collect_toner_items_from_printer_mib(
            host="192.0.2.10",
            settings=MonitoringSettings(snmp_community="community-de-teste"),
            walker=walker,
            snmp_versions=("1", "2c"),
        )

        self.assertEqual(result["versao_snmp"], "1")
        self.assertEqual(result["toners"][0]["percentual"], 64)
        self.assertNotIn("2c", versions)

    def test_v1_sem_percentual_tenta_v2c(self):
        versions = []

        def walker(**kwargs):
            version = kwargs["snmp_version"]
            versions.append(version)
            level = "-2" if version == "1" else "42"
            rows = supply_walk_result(
                [{"description": "Black Toner", "level": level, "max": "100"}]
            )
            return {"sucesso": True, "linhas": rows[kwargs["base_oid"]]}

        result = collect_toner_items_from_printer_mib(
            host="192.0.2.10",
            settings=MonitoringSettings(snmp_community="community-de-teste"),
            walker=walker,
            snmp_versions=("1", "2c"),
        )

        self.assertIn("1", versions)
        self.assertIn("2c", versions)
        self.assertEqual(result["versao_snmp"], "2c")
        self.assertEqual(result["toners"][0]["percentual"], 42)

    def test_sucesso_vazio_nao_impede_proxima_versao(self):
        versions = []

        def walker(**kwargs):
            version = kwargs["snmp_version"]
            versions.append(version)
            if version == "1":
                return {"sucesso": True, "linhas": []}
            rows = supply_walk_result(
                [{"description": "Cyan Toner", "level": "73", "max": "100"}]
            )
            return {"sucesso": True, "linhas": rows[kwargs["base_oid"]]}

        result = collect_toner_items_from_printer_mib(
            host="192.0.2.10",
            settings=MonitoringSettings(snmp_community="community-de-teste"),
            walker=walker,
            snmp_versions=("1", "2c"),
        )

        self.assertIn("2c", versions)
        self.assertEqual(result["toners"][0]["cor"], "cyan")
        self.assertEqual(result["toners"][0]["percentual"], 73)

    def test_falha_em_coluna_auxiliar_nao_impede_level(self):
        consulted_metrics = []
        rows = supply_walk_result(
            [{"description": "Yellow Toner", "level": "58", "max": "100"}]
        )

        def walker(**kwargs):
            base_oid = kwargs["base_oid"]
            consulted_metrics.append(base_oid)
            if base_oid == PRT_MARKER_SUPPLIES_SUPPLY_UNIT_OID:
                return {
                    "sucesso": False,
                    "erro_codigo": "snmp_oid_invalido",
                    "linhas": [],
                }
            return {"sucesso": True, "linhas": rows[base_oid]}

        result = collect_toner_items_from_printer_mib(
            host="192.0.2.10",
            settings=MonitoringSettings(snmp_community="community-de-teste"),
            walker=walker,
            snmp_versions=("1",),
        )

        self.assertIn(PRT_MARKER_SUPPLIES_LEVEL_OID, consulted_metrics)
        self.assertEqual(result["toners"][0]["cor"], "yellow")
        self.assertEqual(result["toners"][0]["percentual"], 58)

    def test_canon_colorida_cruza_as_quatro_cores(self):
        rows = supply_walk_result(
            [
                {"description": "Black Toner", "level": "80"},
                {"description": "Cyan Toner", "level": "70"},
                {"description": "Magenta Toner", "level": "60"},
                {"description": "Yellow Toner", "level": "50"},
            ]
        )

        def walker(**kwargs):
            return {"sucesso": True, "linhas": rows[kwargs["base_oid"]]}

        result = collect_toner_items_from_printer_mib(
            host="192.0.2.10",
            settings=MonitoringSettings(snmp_community="community-de-teste"),
            walker=walker,
            snmp_versions=("1", "2c"),
        )

        self.assertEqual(
            {item["cor"] for item in result["toners"]},
            {"black", "cyan", "magenta", "yellow"},
        )


class TonerFallbackParserTest(TestCase):
    def test_parser_brother_identifica_tonerremain_e_calcula_percentual(self):
        html = '<img class="tonerremain" src="black.gif" height="28">'

        items = parse_brother_tonerremain(html)

        self.assertEqual(BROTHER_TONER_BAR_MAX_HEIGHT, 56)
        self.assertEqual(items[0]["cor"], "black")
        self.assertEqual(items[0]["percentual"], 50)

    def test_parser_brother_monocromatica_assume_preto_sem_cor(self):
        items = parse_brother_tonerremain(
            '<img class="status tonerremain" style="height: 14px">'
        )

        self.assertEqual(items[0]["cor"], "black")
        self.assertEqual(items[0]["percentual"], 25)

    def test_altura_invalida_nao_vira_zero_nem_quebra(self):
        self.assertIsNone(brother_toner_percentage(None))
        self.assertIsNone(brother_toner_percentage("invalida"))
        self.assertIsNone(brother_toner_percentage(0))
        items = parse_brother_tonerremain(
            '<img class="tonerremain" height="invalida">'
        )
        self.assertIsNone(items[0]["percentual"])

    def test_altura_acima_do_maximo_e_limitada_a_cem(self):
        self.assertEqual(brother_toner_percentage(80), 100)

    def test_html_invalido_nao_quebra_parser(self):
        self.assertEqual(parse_brother_tonerremain("<img class='tonerremain'"), [])

    def test_zero_real_e_valido_mas_unknown_nao_e_zero(self):
        self.assertTrue(has_valid_toner_percentage([{"percentual": 0}]))
        self.assertFalse(has_valid_toner_percentage([{"percentual": None}]))


class TonerServiceTest(TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        PrinterModel.__table__.create(engine)
        PrinterMachine.__table__.create(engine)
        StatusImpressora.__table__.create(engine)
        PrinterSnmpOid.__table__.create(engine)
        StatusTonerImpressora.__table__.create(engine)
        HistoricoTonerImpressora.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.redis = FakeRedis()
        self.settings = MonitoringSettings(snmp_community="community-de-teste")

    def tearDown(self):
        self.db.close()

    def add_machine(
        self,
        *,
        status="online",
        ip="192.0.2.10",
        active=True,
        manufacturer="Brother",
        model_name="DCP-L2540DW",
    ):
        model = (
            self.db.query(PrinterModel)
            .filter_by(manufacturer=manufacturer, name=model_name)
            .one_or_none()
        )
        if model is None:
            model = PrinterModel(manufacturer=manufacturer, name=model_name)
        machine = PrinterMachine(
            name="Impressora Toner",
            ip_address=ip,
            printer_model=model,
            is_active=active,
        )
        self.db.add(machine)
        self.db.flush()
        self.db.add(
            StatusImpressora(
                maquina_id=machine.id,
                status_operacional=status,
                nivel_alerta="cinza",
                mensagem_operador="Status de teste.",
            )
        )
        self.db.commit()
        return machine

    def test_sincroniza_status_e_historico_sem_spam(self):
        machine = self.add_machine()
        item = {
            "cor": "black",
            "indice_suprimento": "1.1",
            "descricao_coletada": "Black Toner",
            "tipo_suprimento": "3",
            "nivel_atual": 50,
            "capacidade_maxima": 100,
            "percentual": 50,
            "origem_coleta": "snmp",
            "metodo_coleta": "printer_mib_walk",
            "sucesso": True,
        }

        first = sync_toner_items(self.db, machine=machine, items=[item])
        second = sync_toner_items(self.db, machine=machine, items=[item])

        self.assertEqual(first["historicos_criados"], 1)
        self.assertEqual(second["historicos_criados"], 0)
        self.assertEqual(self.db.query(StatusTonerImpressora).count(), 1)
        self.assertEqual(self.db.query(HistoricoTonerImpressora).count(), 1)

    def test_sincronizacao_remove_projecao_antiga_de_outro_indice(self):
        machine = self.add_machine()
        original = {
            "cor": "black",
            "indice_suprimento": "web_status_1",
            "percentual": None,
            "origem_coleta": "html",
            "metodo_coleta": "web_status",
        }
        sync_toner_items(self.db, machine=machine, items=[original])

        replacement = {
            **original,
            "indice_suprimento": "1.1",
            "percentual": 70,
        }
        sync_toner_items(self.db, machine=machine, items=[replacement])

        rows = self.db.query(StatusTonerImpressora).filter_by(maquina_id=machine.id).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].indice_suprimento, "1.1")
        self.assertEqual(rows[0].percentual, 70)

    def test_maquina_offline_e_ignorada(self):
        machine = self.add_machine(status="offline")

        result = collect_and_sync_machine_toner(
            self.db,
            machine_id=machine.id,
            redis_client=self.redis,
            settings=self.settings,
            walker=Mock(),
        )

        self.assertFalse(result["processada"])
        self.assertEqual(result["motivo"], "offline")

    def test_historico_distingue_percentual_desconhecido(self):
        machine = self.add_machine()
        item = {
            "cor": "black",
            "indice_suprimento": "1.1",
            "descricao_coletada": "Black Toner",
            "percentual": 50,
            "origem_coleta": "snmp",
            "metodo_coleta": "printer_mib_walk",
            "sucesso": True,
        }
        sync_toner_items(self.db, machine=machine, items=[item])

        item["percentual"] = None
        result = sync_toner_items(self.db, machine=machine, items=[item])
        latest = (
            self.db.query(HistoricoTonerImpressora)
            .order_by(HistoricoTonerImpressora.id.desc())
            .first()
        )

        self.assertEqual(result["historicos_criados"], 1)
        self.assertEqual(latest.codigo_evento, "estado_conhecimento_alterado")

    def test_status_alertas_nao_sao_sobrescritos(self):
        machine = self.add_machine()
        status = self.db.query(StatusImpressora).filter_by(maquina_id=machine.id).one()
        status.mensagem_alerta = "Há pouco toner"
        status.nivel_alerta = "amarelo"
        self.db.commit()

        sync_toner_items(
            self.db,
            machine=machine,
            items=[
                {
                    "cor": "black",
                    "indice_suprimento": "1.1",
                    "descricao_coletada": "Black Toner",
                    "percentual": 12,
                    "origem_coleta": "snmp",
                    "metodo_coleta": "printer_mib_walk",
                    "sucesso": True,
                }
            ],
        )

        refreshed = self.db.query(StatusImpressora).filter_by(maquina_id=machine.id).one()
        self.assertEqual(refreshed.mensagem_alerta, "Há pouco toner")
        self.assertEqual(refreshed.nivel_alerta, "amarelo")

    def test_lote_processa_online_e_ignora_offline(self):
        online = self.add_machine(status="online", ip="192.0.2.10")
        self.add_machine(status="offline", ip="192.0.2.11")
        collector = Mock(
            return_value={
                "maquina_id": online.id,
                "processada": True,
                "sincronizado": True,
                "toners_atualizados": 1,
            }
        )

        result = run_toner_batch(
            self.db,
            redis_client=self.redis,
            settings=self.settings,
            collector=collector,
        )

        self.assertEqual(result["processadas"], 1)
        self.assertEqual(result["ignoradas_offline"], 1)
        collector.assert_called_once()

    def test_printer_mib_valido_impede_fallbacks(self):
        machine = self.add_machine()
        snmp_oid = Mock()
        web_status = Mock()
        result = collect_toner_with_fallbacks(
            self.db,
            machine=machine,
            settings=self.settings,
            printer_mib_collector=Mock(
                return_value={"sucesso": True, "toners": [{"percentual": 64}]}
            ),
            snmp_oid_collector=snmp_oid,
            web_status_collector=web_status,
        )

        self.assertEqual(result["camada_toner"], "printer_mib")
        snmp_oid.assert_not_called()
        web_status.assert_not_called()

    def test_canon_ir_c3326i_prioriza_snmp_v1(self):
        machine = self.add_machine(
            manufacturer="Canon",
            model_name="IR-C3326I",
        )
        printer_mib = Mock(
            return_value={"sucesso": True, "toners": [{"percentual": 64}]}
        )

        collect_toner_with_fallbacks(
            self.db,
            machine=machine,
            settings=self.settings,
            printer_mib_collector=printer_mib,
            snmp_oid_collector=Mock(),
            web_status_collector=Mock(),
        )

        printer_mib.assert_called_once_with(
            host=machine.ip_address,
            settings=self.settings,
            snmp_versions=CANON_IR_C3326I_SNMP_VERSIONS,
        )

    def test_printer_mib_sem_percentual_tenta_snmp_oids(self):
        machine = self.add_machine()
        web_status = Mock()
        result = collect_toner_with_fallbacks(
            self.db,
            machine=machine,
            settings=self.settings,
            printer_mib_collector=Mock(
                return_value={"sucesso": True, "toners": [{"percentual": None}]}
            ),
            snmp_oid_collector=Mock(
                return_value={"sucesso": True, "toners": [{"percentual": 42}]}
            ),
            web_status_collector=web_status,
        )

        self.assertEqual(result["camada_toner"], "snmp_oid_fallback")
        web_status.assert_not_called()

    def test_mib_e_snmp_sem_percentual_tentam_web_status(self):
        machine = self.add_machine()
        web_status = Mock(
            return_value={"sucesso": True, "toners": [{"percentual": 50}]}
        )
        result = collect_toner_with_fallbacks(
            self.db,
            machine=machine,
            settings=self.settings,
            printer_mib_collector=Mock(return_value={"sucesso": False, "toners": []}),
            snmp_oid_collector=Mock(return_value={"sucesso": True, "toners": []}),
            web_status_collector=web_status,
        )

        self.assertEqual(result["camada_toner"], "web_status")
        web_status.assert_called_once()

    def test_fallback_substitui_unknown_da_mesma_cor_sem_duplicar(self):
        machine = self.add_machine()
        result = collect_toner_with_fallbacks(
            self.db,
            machine=machine,
            settings=self.settings,
            printer_mib_collector=Mock(
                return_value={
                    "sucesso": True,
                    "toners": [
                        {
                            "cor": "black",
                            "indice_suprimento": "1.1",
                            "percentual": None,
                            "origem_coleta": "snmp",
                            "metodo_coleta": "printer_mib_walk",
                        }
                    ],
                }
            ),
            snmp_oid_collector=Mock(return_value={"sucesso": True, "toners": []}),
            web_status_collector=Mock(
                return_value={
                    "sucesso": True,
                    "toners": [
                        {
                            "cor": "black",
                            "indice_suprimento": "web_status_1",
                            "percentual": 70,
                            "origem_coleta": "html",
                            "metodo_coleta": "web_status",
                        }
                    ],
                }
            ),
        )

        self.assertEqual(len(result["toners"]), 1)
        self.assertEqual(result["toners"][0]["indice_suprimento"], "1.1")
        self.assertEqual(result["toners"][0]["percentual"], 70)
        self.assertEqual(result["toners"][0]["metodo_coleta"], "web_status")

    def test_sem_percentual_preserva_unknown_do_printer_mib(self):
        machine = self.add_machine()
        unknown = {"cor": "black", "percentual": None}
        result = collect_toner_with_fallbacks(
            self.db,
            machine=machine,
            settings=self.settings,
            printer_mib_collector=Mock(return_value={"sucesso": True, "toners": [unknown]}),
            snmp_oid_collector=Mock(return_value={"sucesso": True, "toners": []}),
            web_status_collector=Mock(return_value={"sucesso": True, "toners": []}),
        )

        self.assertIsNone(result["toners"][0]["percentual"])

    @patch(
        "backend.app.modules.printers.monitoring.toner.fallbacks.get_decrypted_html_access_for_model"
    )
    def test_web_status_tenta_apenas_caminhos_aprovados(self, get_access):
        machine = self.add_machine()
        get_access.return_value = HtmlAccessConfig(
            modelo_id=machine.model_id,
            tipo_autenticacao="basic",
            usuario="usuario",
            senha="segredo",
        )
        called_paths = []

        def fetcher(_host, config, **_kwargs):
            called_paths.append(config.caminho_status)
            return HtmlClientResponse(
                sucesso=True,
                status_code=200,
                url_sanitizada=None,
                conteudo_html="<html>sem barra</html>",
                erro_codigo=None,
                erro_detalhe_sanitizado=None,
                protocolo_usado="http",
                tipo_autenticacao="basic",
            )

        collect_toner_from_web_status(self.db, machine=machine, fetcher=fetcher)

        self.assertEqual(tuple(called_paths), WEB_STATUS_PATHS)
        self.assertNotIn("/general/information.html?kind=item", called_paths)

    @patch(
        "backend.app.modules.printers.monitoring.toner.fallbacks.get_decrypted_html_access_for_model"
    )
    @patch(
        "backend.app.modules.printers.monitoring.toner.fallbacks.parse_brother_tonerremain"
    )
    def test_erro_do_parser_html_e_sanitizado_sem_quebrar_lote(self, parser, get_access):
        machine = self.add_machine()
        get_access.return_value = HtmlAccessConfig(
            modelo_id=machine.model_id,
            tipo_autenticacao="basic",
            usuario="usuario",
            senha="segredo",
        )
        parser.side_effect = ValueError("conteudo privado nao deve aparecer")
        response = HtmlClientResponse(
            sucesso=True,
            status_code=200,
            url_sanitizada=None,
            conteudo_html="<html>privado</html>",
            erro_codigo=None,
            erro_detalhe_sanitizado=None,
            protocolo_usado="http",
            tipo_autenticacao="basic",
        )

        result = collect_toner_from_web_status(
            self.db,
            machine=machine,
            fetcher=Mock(return_value=response),
        )

        self.assertEqual(result["erro_codigo"], "toner_web_status_parser_erro")
        self.assertNotIn("privado", str(result))

    def test_oid_brother_invalidado_nao_e_consultado(self):
        machine = self.add_machine()
        self.db.add(
            PrinterSnmpOid(
                modelo_id=machine.model_id,
                chave_metrica="toner_black",
                oid="1.3.6.1.4.1.2435.2.3.9.4.2.1.3.3.1.11.0",
                tipo_valor="gauge",
                versao_snmp="2c",
                modo_consulta="get",
                ativo=True,
            )
        )
        self.db.commit()
        getter = Mock()

        result = collect_toner_from_snmp_oids(
            self.db,
            machine=machine,
            settings=self.settings,
            getter=getter,
        )

        getter.assert_not_called()
        self.assertFalse(has_valid_toner_percentage(result["toners"]))

    def test_oid_ativo_validado_retorna_percentual_sem_dados_brutos(self):
        machine = self.add_machine()
        self.db.add(
            PrinterSnmpOid(
                modelo_id=machine.model_id,
                chave_metrica="toner_black",
                oid="1.3.6.1.2.1.43.11.1.1.9.1.1",
                tipo_valor="gauge",
                versao_snmp="2c",
                modo_consulta="get",
                ativo=True,
            )
        )
        self.db.commit()
        result = collect_toner_from_snmp_oids(
            self.db,
            machine=machine,
            settings=self.settings,
            getter=Mock(
                return_value={
                    "sucesso": True,
                    "alertas_brutos": [{"valor_original": "37", "oid_retornado": "oculto"}],
                }
            ),
        )

        self.assertEqual(result["toners"][0]["percentual"], 37)
        self.assertNotIn("oid_retornado", result["toners"][0])
        self.assertNotIn("valor_original", result["toners"][0])

    def test_logs_da_cascata_nao_expoem_credenciais(self):
        machine = self.add_machine()
        with self.assertLogs(
            "backend.app.modules.printers.monitoring.toner.services",
            level="INFO",
        ) as captured:
            collect_toner_with_fallbacks(
                self.db,
                machine=machine,
                settings=self.settings,
                printer_mib_collector=Mock(return_value={"sucesso": True, "toners": []}),
                snmp_oid_collector=Mock(return_value={"sucesso": True, "toners": []}),
                web_status_collector=Mock(return_value={"sucesso": True, "toners": []}),
            )

        logs = " ".join(captured.output)
        self.assertNotIn(self.settings.snmp_community, logs)
        self.assertNotIn("Authorization", logs)


class TonerCeleryScheduleTest(TestCase):
    def test_task_toner_60min_registrada_e_agendada(self):
        schedule = celery_app.conf.beat_schedule["printers-toner-every-60-minutes"]

        self.assertIn("printers_toner_all", celery_app.tasks)
        self.assertEqual(printers_toner_all.name, "printers_toner_all")
        self.assertEqual(schedule["task"], "printers_toner_all")
        self.assertEqual(schedule["schedule"], 3600.0)

    @patch("backend.app.modules.printers.monitoring.tasks.get_redis_client")
    def test_lock_global_toner_impede_sobreposicao(self, get_client):
        redis_client = FakeRedis()
        redis_client.set("printers:lock:toner:global", "outra-execucao")
        get_client.return_value = redis_client

        result = printers_toner_all.run()

        self.assertFalse(result["executada"])
        self.assertEqual(result["motivo"], "lock_global_ativo")
