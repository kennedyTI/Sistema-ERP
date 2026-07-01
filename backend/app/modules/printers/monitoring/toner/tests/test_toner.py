from unittest import TestCase
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.celery_app import celery_app
from backend.app.modules.printers.machines.models import PrinterMachine, PrinterModel
from backend.app.modules.printers.monitoring.config import MonitoringSettings
from backend.app.modules.printers.monitoring.tasks import printers_toner_all
from backend.app.modules.printers.monitoring.toner.collector import (
    PRT_MARKER_SUPPLIES_DESCRIPTION_OID,
    PRT_MARKER_SUPPLIES_LEVEL_OID,
    PRT_MARKER_SUPPLIES_MAX_CAPACITY_OID,
    PRT_MARKER_SUPPLIES_SUPPLY_UNIT_OID,
    PRT_MARKER_SUPPLIES_TYPE_OID,
    calculate_toner_percentage,
    is_toner_supply,
    resolve_toner_color,
    toner_items_from_mib_rows,
)
from backend.app.modules.printers.monitoring.toner.models import (
    HistoricoTonerImpressora,
    StatusTonerImpressora,
)
from backend.app.modules.printers.monitoring.toner.services import (
    collect_and_sync_machine_toner,
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
        StatusTonerImpressora.__table__.create(engine)
        HistoricoTonerImpressora.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.redis = FakeRedis()
        self.settings = MonitoringSettings(snmp_community="community-de-teste")

    def tearDown(self):
        self.db.close()

    def add_machine(self, *, status="online", ip="192.0.2.10", active=True):
        model = (
            self.db.query(PrinterModel)
            .filter_by(manufacturer="Brother", name="DCP-L2540DW")
            .one_or_none()
        )
        if model is None:
            model = PrinterModel(manufacturer="Brother", name="DCP-L2540DW")
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
