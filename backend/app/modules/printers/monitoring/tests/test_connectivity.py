import json
from contextlib import nullcontext
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.modules.printers.machines.models import PrinterMachine, PrinterModel
from backend.app.modules.printers.monitoring.config import MonitoringSettings
from backend.app.modules.printers.monitoring.probes import detect_connectivity
from backend.app.modules.printers.monitoring.schemas import (
    ConnectivityDetection,
    ProbeResult,
)
from backend.app.modules.printers.monitoring.services import (
    monitor_machine_connectivity,
    run_connectivity_batch,
)
from backend.app.modules.printers.monitoring.tasks import printers_connectivity_all
from backend.app.modules.printers.status.admin import PrinterStatusHistoryAdmin
from backend.app.modules.printers.status.django_models import (
    PrinterStatusHistoryAdminModel,
)
from backend.app.modules.printers.status.models import (
    HistoricoStatusImpressora,
    LogImpressora,
    StatusImpressora,
)


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

    def get(self, key):
        return self.values.get(key)

    def eval(self, _script, _key_count, key, token):
        if self.values.get(key) != token:
            return 0
        del self.values[key]
        self.ttls.pop(key, None)
        return 1

    def ping(self):
        return True


def failed_detection(_host, _settings):
    return ConnectivityDetection(
        online=False,
        method="fallback",
        latency_ms=None,
        attempts={
            "icmp": {"executado": True, "sucesso": False, "erro": "timeout"},
            "tcp": {"executado": True, "sucesso": False, "erro": "sem_resposta"},
            "snmp": {"executado": True, "sucesso": False, "erro": "sem_resposta"},
            "html": {"executado": True, "sucesso": False, "erro": "sem_resposta"},
        },
    )


def online_detection(method="icmp", latency_ms=12):
    return ConnectivityDetection(
        online=True,
        method=method,
        latency_ms=latency_ms,
        attempts={
            "icmp": {
                "executado": True,
                "sucesso": method == "icmp",
                "latencia_ms": latency_ms if method == "icmp" else None,
            },
            "tcp": {"executado": method in {"tcp", "snmp", "html"}, "sucesso": method == "tcp"},
            "snmp": {"executado": method in {"snmp", "html"}, "sucesso": method == "snmp"},
            "html": {"executado": method == "html", "sucesso": method == "html"},
        },
    )


class PrinterConnectivityTest(TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        PrinterModel.__table__.create(engine)
        PrinterMachine.__table__.create(engine)
        StatusImpressora.__table__.create(engine)
        HistoricoStatusImpressora.__table__.create(engine)
        LogImpressora.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.redis = FakeRedis()
        self.settings = MonitoringSettings()

    def tearDown(self):
        self.db.close()

    def add_machine(self, *, active=True, status="desconhecido", ip_address=None):
        model = PrinterModel(
            manufacturer="Fabricante Exemplo",
            name=f"Modelo {self.db.query(PrinterModel).count() + 1}",
        )
        machine = PrinterMachine(
            name=f"Impressora {self.db.query(PrinterMachine).count() + 1}",
            ip_address=ip_address or f"192.0.2.{self.db.query(PrinterMachine).count() + 10}",
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
                mensagem_operador="Aguardando primeira verificacao.",
            )
        )
        self.db.commit()
        return machine

    @patch("backend.app.modules.printers.monitoring.probes.probe_html")
    @patch("backend.app.modules.printers.monitoring.probes.probe_snmp")
    @patch("backend.app.modules.printers.monitoring.probes.probe_tcp")
    @patch("backend.app.modules.printers.monitoring.probes.probe_icmp")
    def test_01_maquina_online_por_icmp(self, icmp, tcp, snmp, html):
        icmp.return_value = ProbeResult("icmp", True, latency_ms=4)

        result = detect_connectivity("192.0.2.10", self.settings)

        self.assertTrue(result.online)
        self.assertEqual(result.method, "icmp")
        tcp.assert_not_called()
        snmp.assert_not_called()
        html.assert_not_called()

    @patch("backend.app.modules.printers.monitoring.probes.socket.create_connection")
    @patch("backend.app.modules.printers.monitoring.probes.probe_icmp")
    def test_02_maquina_online_por_tcp_443(self, icmp, create_connection):
        icmp.return_value = ProbeResult("icmp", False, error="timeout")
        create_connection.return_value = nullcontext()

        result = detect_connectivity("192.0.2.10", self.settings)

        self.assertEqual(result.method, "tcp")
        self.assertEqual(result.attempts["tcp"]["porta"], 443)
        create_connection.assert_called_once_with(("192.0.2.10", 443), timeout=1.0)

    @patch("backend.app.modules.printers.monitoring.probes.socket.create_connection")
    @patch("backend.app.modules.printers.monitoring.probes.probe_icmp")
    def test_03_maquina_online_por_tcp_80(self, icmp, create_connection):
        icmp.return_value = ProbeResult("icmp", False, error="timeout")
        create_connection.side_effect = [OSError(), nullcontext()]

        result = detect_connectivity("192.0.2.10", self.settings)

        self.assertEqual(result.method, "tcp")
        self.assertEqual(result.attempts["tcp"]["porta"], 80)
        self.assertEqual(
            [call.args[0][1] for call in create_connection.call_args_list],
            [443, 80],
        )

    @patch("backend.app.modules.printers.monitoring.probes.probe_html")
    @patch("backend.app.modules.printers.monitoring.probes.probe_snmp")
    @patch("backend.app.modules.printers.monitoring.probes.probe_tcp")
    @patch("backend.app.modules.printers.monitoring.probes.probe_icmp")
    def test_04_maquina_online_por_snmp(self, icmp, tcp, snmp, html):
        icmp.return_value = ProbeResult("icmp", False, error="timeout")
        tcp.return_value = ProbeResult("tcp", False, error="sem_resposta")
        snmp.return_value = ProbeResult("snmp", True, latency_ms=8)

        result = detect_connectivity("192.0.2.10", self.settings)

        self.assertEqual(result.method, "snmp")
        html.assert_not_called()

    @patch("backend.app.modules.printers.monitoring.probes.probe_html")
    @patch("backend.app.modules.printers.monitoring.probes.probe_snmp")
    @patch("backend.app.modules.printers.monitoring.probes.probe_tcp")
    @patch("backend.app.modules.printers.monitoring.probes.probe_icmp")
    def test_05_maquina_online_por_html(self, icmp, tcp, snmp, html):
        icmp.return_value = ProbeResult("icmp", False, error="timeout")
        tcp.return_value = ProbeResult("tcp", False, error="sem_resposta")
        snmp.return_value = ProbeResult("snmp", False, error="sem_resposta")
        html.return_value = ProbeResult("html", True, latency_ms=15)

        result = detect_connectivity("192.0.2.10", self.settings)

        self.assertEqual(result.method, "html")

    def test_06_primeira_falha_fica_suspeita_apenas_no_redis(self):
        machine = self.add_machine()

        result = monitor_machine_connectivity(
            self.db,
            machine,
            redis_client=self.redis,
            settings=self.settings,
            detector=failed_detection,
        )

        self.assertEqual(result["status"], "offline_suspeito")
        cached = json.loads(self.redis.get(f"printers:connectivity:{machine.id}"))
        self.assertEqual(cached["status_detectado"], "offline_suspeito")
        self.assertEqual(self.db.query(HistoricoStatusImpressora).count(), 0)

    def test_07_segunda_falha_confirma_offline(self):
        machine = self.add_machine()
        for _ in range(2):
            result = monitor_machine_connectivity(
                self.db,
                machine,
                redis_client=self.redis,
                settings=self.settings,
                detector=failed_detection,
            )

        self.assertEqual(result["status"], "offline")
        status = self.db.query(StatusImpressora).filter_by(maquina_id=machine.id).one()
        history = self.db.query(HistoricoStatusImpressora).one()
        self.assertEqual(status.status_operacional, "offline")
        self.assertEqual(history.codigo_evento, "desconhecido_para_offline")
        self.assertEqual(history.metodo_confirmacao, "fallback")

    def test_08_offline_volta_online_imediatamente(self):
        machine = self.add_machine(status="offline")

        result = monitor_machine_connectivity(
            self.db,
            machine,
            redis_client=self.redis,
            settings=self.settings,
            detector=lambda host, settings: online_detection("tcp"),
        )

        self.assertEqual(result["status"], "online")
        self.assertEqual(result["falhas_consecutivas"], 0)
        self.assertEqual(self.db.query(HistoricoStatusImpressora).one().codigo_evento, "online_confirmado")

    def test_09_maquina_inativa_nao_e_processada(self):
        machine = self.add_machine(active=False)

        result = monitor_machine_connectivity(
            self.db,
            machine,
            redis_client=self.redis,
            detector=lambda host, settings: online_detection(),
        )

        self.assertFalse(result["processada"])
        self.assertNotIn(f"printers:connectivity:{machine.id}", self.redis.values)

    @patch("backend.app.modules.printers.monitoring.services.monitor_machine_connectivity")
    def test_10_falha_em_maquina_nao_interrompe_lote(self, monitor):
        first = self.add_machine()
        second = self.add_machine()
        monitor.side_effect = [
            RuntimeError("falha simulada"),
            {"maquina_id": second.id, "processada": True, "status": "online"},
        ]

        result = run_connectivity_batch(self.db, redis_client=self.redis)

        self.assertEqual(result["total_ativas"], 2)
        self.assertEqual(result["resultados"][0]["maquina_id"], first.id)
        self.assertEqual(result["resultados"][0]["motivo"], "erro_processamento")
        self.assertTrue(result["resultados"][1]["processada"])

    @patch("backend.app.modules.printers.monitoring.tasks.get_redis_client")
    def test_11_lock_global_impede_execucao_concorrente(self, get_client):
        get_client.return_value = self.redis
        self.redis.set("printers:lock:connectivity:global", "outra-execucao")

        result = printers_connectivity_all.run()

        self.assertFalse(result["executada"])
        self.assertEqual(result["motivo"], "lock_global_ativo")

    def test_12_lock_por_maquina_impede_dupla_coleta(self):
        machine = self.add_machine()
        self.redis.set(
            f"printers:lock:connectivity:machine:{machine.id}",
            "outra-execucao",
        )

        result = run_connectivity_batch(self.db, redis_client=self.redis)

        self.assertEqual(result["processadas"], 0)
        self.assertEqual(result["resultados"][0]["motivo"], "lock_ativo")

    def test_13_redis_atualiza_em_todo_ciclo(self):
        machine = self.add_machine()

        monitor_machine_connectivity(
            self.db,
            machine,
            redis_client=self.redis,
            settings=self.settings,
            detector=lambda host, settings: online_detection("icmp"),
        )

        key = f"printers:connectivity:{machine.id}"
        self.assertIn(key, self.redis.values)
        self.assertEqual(self.redis.ttls[key], 90)

    def test_14_status_atualiza_quando_confirmado(self):
        machine = self.add_machine()

        monitor_machine_connectivity(
            self.db,
            machine,
            redis_client=self.redis,
            detector=lambda host, settings: online_detection("snmp", 7),
        )

        status = self.db.query(StatusImpressora).filter_by(maquina_id=machine.id).one()
        self.assertEqual(status.status_operacional, "online")
        self.assertEqual(status.metodo_confirmacao, "snmp")
        self.assertEqual(status.tempo_resposta_ms, 7)
        self.assertIsNotNone(status.ultima_verificacao_em)

    def test_15_historico_so_grava_quando_status_muda(self):
        machine = self.add_machine(status="online")

        monitor_machine_connectivity(
            self.db,
            machine,
            redis_client=self.redis,
            detector=lambda host, settings: online_detection("icmp"),
        )

        self.assertEqual(self.db.query(HistoricoStatusImpressora).count(), 0)

    def test_16_suspeita_nao_altera_status_nem_historico(self):
        machine = self.add_machine(status="online")

        monitor_machine_connectivity(
            self.db,
            machine,
            redis_client=self.redis,
            detector=failed_detection,
        )

        status = self.db.query(StatusImpressora).filter_by(maquina_id=machine.id).one()
        self.assertEqual(status.status_operacional, "online")
        self.assertEqual(self.db.query(HistoricoStatusImpressora).count(), 0)

    def test_17_admin_do_historico_e_somente_leitura(self):
        model_admin = PrinterStatusHistoryAdmin(
            PrinterStatusHistoryAdminModel,
            AdminSite(),
        )

        self.assertFalse(model_admin.has_add_permission(MagicMock()))
        self.assertFalse(model_admin.has_change_permission(MagicMock()))
        self.assertFalse(model_admin.has_delete_permission(MagicMock()))

    def test_18_indices_do_historico_estao_declarados(self):
        index_names = {
            index.name for index in HistoricoStatusImpressora.__table__.indexes
        }

        self.assertEqual(
            index_names,
            {
                "ix_historico_status_impressoras_maquina_id",
                "ix_historico_status_impressoras_verificado_em",
                "ix_historico_status_impressoras_status_novo",
                "ix_historico_status_impressoras_maquina_verificado",
            },
        )
