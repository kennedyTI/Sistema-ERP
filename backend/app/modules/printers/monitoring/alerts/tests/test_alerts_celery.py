from unittest import TestCase
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.celery_app import celery_app
from backend.app.modules.printers.machines.models import PrinterMachine, PrinterModel
from backend.app.modules.printers.monitoring.alerts.services import run_alerts_batch
from backend.app.modules.printers.monitoring.config import MonitoringSettings
from backend.app.modules.printers.monitoring.snmp.models import PrinterSnmpOid
from backend.app.modules.printers.monitoring.tasks import (
    printers_alerts_all,
    printers_connectivity_all,
)
from backend.app.modules.printers.status.models import StatusImpressora


SENSITIVE_MARKER = "community-nao-deve-aparecer"
ALERT_BASE_OID = "1.3.6.1.2.1.43.18.1.1.8"


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


class AlertCeleryScheduleTest(TestCase):
    def test_task_conectividade_60s_registrada_e_agendada(self):
        schedule = celery_app.conf.beat_schedule[
            "printers-connectivity-every-60-seconds"
        ]

        self.assertIn("printers_connectivity_all", celery_app.tasks)
        self.assertEqual(printers_connectivity_all.name, "printers_connectivity_all")
        self.assertEqual(schedule["task"], "printers_connectivity_all")
        self.assertEqual(schedule["schedule"], 60.0)

    def test_task_alertas_5min_registrada_e_agendada(self):
        schedule = celery_app.conf.beat_schedule["printers-alerts-every-5-minutes"]

        self.assertIn("printers_alerts_all", celery_app.tasks)
        self.assertEqual(printers_alerts_all.name, "printers_alerts_all")
        self.assertEqual(schedule["task"], "printers_alerts_all")
        self.assertEqual(schedule["schedule"], 300.0)

    @patch("backend.app.modules.printers.monitoring.tasks.get_redis_client")
    def test_lock_global_alertas_impede_sobreposicao(self, get_client):
        redis_client = FakeRedis()
        redis_client.set("printers:lock:alerts:global", "outra-execucao")
        get_client.return_value = redis_client

        result = printers_alerts_all.run()

        self.assertFalse(result["executada"])
        self.assertEqual(result["motivo"], "lock_global_ativo")


class AlertCeleryBatchTest(TestCase):
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
        self.db = sessionmaker(bind=engine)()
        self.redis = FakeRedis()
        self.settings = MonitoringSettings(snmp_community=SENSITIVE_MARKER)

    def tearDown(self):
        self.db.close()

    def add_model(self, name="Modelo"):
        model = PrinterModel(manufacturer="Fabricante", name=name)
        self.db.add(model)
        self.db.commit()
        return model

    def add_machine(
        self,
        *,
        model=None,
        active=True,
        ip="192.0.2.10",
        status="online",
        oid=True,
    ):
        if model is None and oid:
            model = self.add_model(name=f"Modelo {self.db.query(PrinterModel).count() + 1}")
        machine = PrinterMachine(
            name=f"Impressora {self.db.query(PrinterMachine).count() + 1}",
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
        if oid and model is not None:
            self.db.add(
                PrinterSnmpOid(
                    modelo_id=model.id,
                    chave_metrica="alert_raw",
                    oid=ALERT_BASE_OID,
                    tipo_valor="string",
                    versao_snmp="2c",
                    modo_consulta="walk",
                    ativo=True,
                )
            )
        self.db.commit()
        return machine

    def successful_result(self, machine_id):
        return {
            "maquina_id": machine_id,
            "processada": True,
            "sincronizado": True,
            "falha_tecnica_consolidada": False,
            "classificacao_nova": "verde",
            "tentativas_snmp": 1,
        }

    def test_busca_apenas_maquinas_ativas(self):
        active = self.add_machine(ip="192.0.2.10")
        self.add_machine(active=False, ip="192.0.2.11")
        collector = Mock(return_value=self.successful_result(active.id))

        result = run_alerts_batch(
            self.db,
            redis_client=self.redis,
            settings=self.settings,
            collector=collector,
        )

        self.assertEqual(result["total_maquinas"], 1)
        collector.assert_called_once()
        self.assertEqual(collector.call_args.kwargs["machine_id"], active.id)

    def test_ignora_maquina_offline_pelo_status_atual(self):
        machine = self.add_machine(status="offline")
        collector = Mock(return_value=self.successful_result(machine.id))

        result = run_alerts_batch(
            self.db,
            redis_client=self.redis,
            settings=self.settings,
            collector=collector,
        )

        collector.assert_not_called()
        self.assertEqual(result["ignoradas"], 1)
        self.assertEqual(result["resultados"][0]["motivo"], "offline")

    def test_ignora_maquinas_sem_ip_sem_modelo_ou_sem_oid(self):
        self.add_machine(ip="", oid=True)
        self.add_machine(model=None, ip="192.0.2.20", oid=False)
        model = self.add_model("Modelo sem OID")
        self.add_machine(model=model, ip="192.0.2.30", oid=False)

        result = run_alerts_batch(
            self.db,
            redis_client=self.redis,
            settings=self.settings,
            collector=Mock(),
        )

        self.assertEqual(result["ignoradas"], 3)
        self.assertEqual(
            [item["motivo"] for item in result["resultados"]],
            ["sem_ip", "sem_modelo", "sem_oid_alert_raw"],
        )

    def test_chama_orquestrador_para_maquina_elegivel(self):
        machine = self.add_machine()
        collector = Mock(return_value=self.successful_result(machine.id))

        result = run_alerts_batch(
            self.db,
            redis_client=self.redis,
            settings=self.settings,
            collector=collector,
        )

        self.assertEqual(result["processadas"], 1)
        self.assertEqual(result["sucesso"], 1)
        collector.assert_called_once_with(
            self.db,
            machine_id=machine.id,
            redis_client=self.redis,
            settings=self.settings,
        )

    def test_falha_em_maquina_nao_quebra_lote(self):
        first = self.add_machine(ip="192.0.2.10")
        second = self.add_machine(ip="192.0.2.11")
        collector = Mock(
            side_effect=[
                RuntimeError("falha simulada"),
                self.successful_result(second.id),
            ]
        )

        result = run_alerts_batch(
            self.db,
            redis_client=self.redis,
            settings=self.settings,
            collector=collector,
        )

        self.assertEqual(result["total_maquinas"], 2)
        self.assertEqual(result["processadas"], 1)
        self.assertEqual(result["sucesso"], 1)
        self.assertEqual(result["falha"], 1)
        self.assertEqual(result["resultados"][0]["maquina_id"], first.id)
        self.assertEqual(result["resultados"][0]["motivo"], "erro_processamento")

    def test_retorna_resumo_de_execucao(self):
        success = self.add_machine(ip="192.0.2.10")
        technical_failure = self.add_machine(ip="192.0.2.11")
        self.add_machine(status="offline", ip="192.0.2.12")
        collector = Mock(
            side_effect=[
                self.successful_result(success.id),
                {
                    "maquina_id": technical_failure.id,
                    "processada": True,
                    "sincronizado": True,
                    "falha_tecnica_consolidada": True,
                    "classificacao_nova": "vermelho",
                    "tentativas_snmp": 2,
                },
            ]
        )

        result = run_alerts_batch(
            self.db,
            redis_client=self.redis,
            settings=self.settings,
            collector=collector,
        )

        self.assertEqual(result["total_maquinas"], 3)
        self.assertEqual(result["processadas"], 2)
        self.assertEqual(result["ignoradas"], 1)
        self.assertEqual(result["sucesso"], 1)
        self.assertEqual(result["falha"], 1)
        self.assertEqual(len(result["resultados"]), 3)

    def test_lock_por_maquina_e_respeitado_pelo_orquestrador(self):
        machine = self.add_machine()
        self.redis.set(f"printers:lock:alerts:machine:{machine.id}", "ativo")

        result = run_alerts_batch(
            self.db,
            redis_client=self.redis,
            settings=self.settings,
        )

        self.assertEqual(result["processadas"], 0)
        self.assertEqual(result["ignoradas"], 1)
        self.assertEqual(result["resultados"][0]["motivo"], "lock_ativo")

    def test_retorno_serializado_nao_expoe_community(self):
        machine = self.add_machine()
        collector = Mock(
            return_value={
                "maquina_id": machine.id,
                "processada": False,
                "motivo": "erro_processamento",
                "erro_codigo": "snmp_community_invalida",
                "erro_detalhe": f"community {SENSITIVE_MARKER}",
            }
        )

        result = run_alerts_batch(
            self.db,
            redis_client=self.redis,
            settings=self.settings,
            collector=collector,
        )

        self.assertNotIn(SENSITIVE_MARKER, str(result))

