from unittest import TestCase

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.modules.printers.machines.models import PrinterMachine, PrinterModel
from backend.app.modules.printers.monitoring.config import MonitoringSettings
from backend.app.modules.printers.monitoring.snmp.alert_collector import (
    collect_snmp_alerts_for_machine,
)
from backend.app.modules.printers.monitoring.snmp.models import PrinterSnmpOid
from backend.app.modules.printers.monitoring.state.models import PrinterAlertRule
from backend.app.modules.printers.status.models import StatusImpressora


SENSITIVE_MARKER = "valor-sensivel-de-teste"
ALERT_BASE_OID = "1.3.6.1.2.1.43.18.1.1.8"


def raw_alert(
    message: str,
    *,
    oid: str = f"{ALERT_BASE_OID}.1.1",
    value_repr: str | None = None,
) -> dict:
    return {
        "oid_retornado": oid,
        "valor_original": message,
        "valor_repr": value_repr or repr(message),
        "tipo_snmp": "OctetString",
    }


def snmp_success(alerts: list[dict], latency_ms: int = 42) -> dict:
    return {
        "sucesso": True,
        "alertas_brutos": alerts,
        "latencia_ms": latency_ms,
    }


def snmp_failure(
    *,
    error_code: str = "snmp_timeout",
    error_detail: str = "Tempo limite excedido ao consultar SNMP.",
    latency_ms: int = 3000,
) -> dict:
    return {
        "sucesso": False,
        "erro_codigo": error_code,
        "erro_detalhe": error_detail,
        "latencia_ms": latency_ms,
    }


class RecordingCollector:
    def __init__(self, result: dict):
        self.result = result
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class SnmpAlertCollectorTest(TestCase):
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
        PrinterAlertRule.__table__.create(engine)
        self.engine = engine
        self.db = sessionmaker(bind=engine)()
        self.settings = MonitoringSettings(
            snmp_community=SENSITIVE_MARKER,
            snmp_timeout_seconds=1.0,
        )
        self.model = self.add_model()
        self.machine = self.add_machine(model=self.model)
        self.add_status(self.machine, "online")
        self.add_oid(self.model, mode="walk")
        self.add_default_rules()

    def tearDown(self):
        self.db.close()

    def add_model(self, *, manufacturer="Fabricante", name="Modelo") -> PrinterModel:
        model = PrinterModel(manufacturer=manufacturer, name=name)
        self.db.add(model)
        self.db.commit()
        return model

    def add_machine(
        self,
        *,
        model: PrinterModel | None,
        active: bool = True,
        ip_address: str | None = "192.0.2.10",
    ) -> PrinterMachine:
        machine = PrinterMachine(
            name=f"Impressora {self.db.query(PrinterMachine).count() + 1}",
            ip_address=ip_address or "",
            printer_model=model,
            is_active=active,
        )
        self.db.add(machine)
        self.db.commit()
        return machine

    def add_status(self, machine: PrinterMachine, status: str) -> StatusImpressora:
        row = StatusImpressora(
            maquina_id=machine.id,
            status_operacional=status,
            nivel_alerta="cinza",
            mensagem_operador="Status de teste.",
        )
        self.db.add(row)
        self.db.commit()
        return row

    def add_oid(
        self,
        model: PrinterModel,
        *,
        mode: str,
        active: bool = True,
        oid: str = ALERT_BASE_OID,
    ) -> PrinterSnmpOid:
        row = PrinterSnmpOid(
            modelo_id=model.id,
            chave_metrica="alert_raw",
            oid=oid,
            tipo_valor="string",
            versao_snmp="2c",
            modo_consulta=mode,
            ativo=active,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def add_rule(
        self,
        code: str,
        pattern: str,
        *,
        severity: str,
        priority: int = 50,
        description: str | None = None,
    ) -> PrinterAlertRule:
        rule = PrinterAlertRule(
            codigo=code,
            descricao=description or code,
            severidade=severity,
            tipo_regra="contains",
            padrao=pattern,
            prioridade=priority,
            ativo=True,
        )
        self.db.add(rule)
        self.db.commit()
        return rule

    def add_default_rules(self):
        self.add_rule(
            "replace_toner",
            "substituir toner",
            severity="high",
            priority=10,
            description="Substituir toner",
        )
        self.add_rule(
            "toner_low",
            "toner baixo",
            severity="medium",
            priority=20,
            description="Toner baixo",
        )
        self.add_rule(
            "idle",
            "em espera",
            severity="green",
            priority=100,
            description="Estado normal / em espera",
        )
        self.add_rule(
            "unknown",
            "",
            severity="medium",
            priority=999,
            description="Alerta nao reconhecido",
        )

    def collect(self, machine_id=None, *, get_result=None, walk_result=None):
        snmp_get = RecordingCollector(get_result or snmp_success([]))
        snmp_walk = RecordingCollector(walk_result or snmp_success([]))
        result = collect_snmp_alerts_for_machine(
            self.db,
            machine_id=machine_id or self.machine.id,
            settings=self.settings,
            snmp_get=snmp_get,
            snmp_walk=snmp_walk,
        )
        return result, snmp_get, snmp_walk

    def test_retorna_erro_controlado_para_maquina_inexistente(self):
        result, _, _ = self.collect(machine_id=999)

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "maquina_nao_encontrada")

    def test_retorna_erro_controlado_para_maquina_inativa(self):
        inactive = self.add_machine(model=self.model, active=False, ip_address="192.0.2.11")

        result, _, _ = self.collect(machine_id=inactive.id)

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "maquina_inativa")

    def test_retorna_erro_controlado_para_maquina_sem_ip(self):
        machine = self.add_machine(model=self.model, ip_address="")

        result, _, _ = self.collect(machine_id=machine.id)

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "maquina_sem_ip")

    def test_retorna_erro_controlado_para_maquina_sem_modelo(self):
        machine = self.add_machine(model=None, ip_address="192.0.2.12")

        result, _, _ = self.collect(machine_id=machine.id)

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "maquina_sem_modelo")

    def test_retorna_erro_controlado_para_modelo_sem_oid_alert_raw_ativo(self):
        model = self.add_model(name="Modelo sem OID")
        machine = self.add_machine(model=model, ip_address="192.0.2.13")

        result, _, _ = self.collect(machine_id=machine.id)

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "oid_alert_raw_nao_configurado")

    def test_retorna_erro_controlado_para_maquina_offline(self):
        model = self.add_model(name="Modelo offline")
        machine = self.add_machine(model=model, ip_address="192.0.2.14")
        self.add_status(machine, "offline")
        self.add_oid(model, mode="walk")

        result, _, _ = self.collect(machine_id=machine.id)

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "maquina_offline")

    def test_usa_modo_consulta_get_para_chamar_snmp_get(self):
        self.db.query(PrinterSnmpOid).filter_by(modelo_id=self.model.id).one().modo_consulta = "get"
        self.db.commit()

        result, snmp_get, snmp_walk = self.collect(
            get_result=snmp_success([raw_alert("Em espera")])
        )

        self.assertTrue(result["sucesso"])
        self.assertEqual(len(snmp_get.calls), 1)
        self.assertEqual(len(snmp_walk.calls), 0)
        self.assertEqual(result["modo_consulta"], "get")

    def test_usa_modo_consulta_walk_para_chamar_snmp_walk(self):
        result, snmp_get, snmp_walk = self.collect(
            walk_result=snmp_success([raw_alert("Em espera")])
        )

        self.assertTrue(result["sucesso"])
        self.assertEqual(len(snmp_get.calls), 0)
        self.assertEqual(len(snmp_walk.calls), 1)
        self.assertEqual(result["modo_consulta"], "walk")

    def test_get_com_valor_retorna_alertas_brutos_com_um_item(self):
        self.db.query(PrinterSnmpOid).filter_by(modelo_id=self.model.id).one().modo_consulta = "get"
        self.db.commit()

        result, _, _ = self.collect(get_result=snmp_success([raw_alert("Em espera")]))

        self.assertEqual(len(result["alertas_brutos"]), 1)
        self.assertEqual(result["alertas_brutos"][0]["valor_original"], "Em espera")

    def test_walk_com_um_valor_retorna_lista_com_um_item(self):
        result, _, _ = self.collect(walk_result=snmp_success([raw_alert("Em espera")]))

        self.assertEqual(len(result["alertas_brutos"]), 1)

    def test_walk_com_multiplos_valores_retorna_lista_com_multiplos_itens(self):
        result, _, _ = self.collect(
            walk_result=snmp_success(
                [
                    raw_alert("Substituir toner", oid=f"{ALERT_BASE_OID}.1.1"),
                    raw_alert("Toner baixo", oid=f"{ALERT_BASE_OID}.1.2"),
                ]
            )
        )

        self.assertEqual(len(result["alertas_brutos"]), 2)
        self.assertEqual(
            [item["oid_retornado"] for item in result["alertas_brutos"]],
            [f"{ALERT_BASE_OID}.1.1", f"{ALERT_BASE_OID}.1.2"],
        )

    def test_walk_vazio_gera_sem_retorno_alerta_cinza(self):
        result, _, _ = self.collect(walk_result=snmp_success([]))

        self.assertTrue(result["sucesso"])
        self.assertEqual(result["alertas_normalizados"][0]["codigo"], "sem_retorno_alerta")
        self.assertEqual(result["classificacao_geral"], "cinza")

    def test_get_vazio_gera_sem_retorno_alerta_cinza(self):
        self.db.query(PrinterSnmpOid).filter_by(modelo_id=self.model.id).one().modo_consulta = "get"
        self.db.commit()

        result, _, _ = self.collect(get_result=snmp_success([]))

        self.assertTrue(result["sucesso"])
        self.assertEqual(result["alertas_normalizados"][0]["codigo"], "sem_retorno_alerta")
        self.assertEqual(result["classificacao_geral"], "cinza")

    def test_mensagem_conhecida_aplica_rules_engine_corretamente(self):
        result, _, _ = self.collect(
            walk_result=snmp_success([raw_alert("Substituir toner")])
        )

        normalized = result["alertas_normalizados"][0]
        self.assertEqual(normalized["codigo"], "replace_toner")
        self.assertEqual(normalized["severidade"], "high")
        self.assertEqual(normalized["classificacao"], "vermelho")
        self.assertTrue(normalized["reconhecido"])

    def test_mensagem_unknown_vira_codigo_unknown_e_classificacao_cinza(self):
        result, _, _ = self.collect(
            walk_result=snmp_success([raw_alert("Replace Waste Toner Box")])
        )

        normalized = result["alertas_normalizados"][0]
        self.assertEqual(normalized["codigo"], "unknown")
        self.assertEqual(normalized["severidade"], "unknown")
        self.assertEqual(normalized["classificacao"], "cinza")

    def test_unknown_nao_retorna_sucesso_false(self):
        result, _, _ = self.collect(
            walk_result=snmp_success([raw_alert("Mensagem nao catalogada")])
        )

        self.assertTrue(result["sucesso"])
        self.assertEqual(result["classificacao_geral"], "cinza")

    def test_timeout_snmp_retorna_falha_tecnica_controlada(self):
        result, _, _ = self.collect(walk_result=snmp_failure(error_code="snmp_timeout"))

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "snmp_timeout")
        self.assertNotIn("alertas_normalizados", result)

    def test_erro_de_community_ou_sem_resposta_retorna_falha_tecnica_controlada(self):
        result, _, _ = self.collect(
            walk_result=snmp_failure(
                error_code="snmp_community_invalida",
                error_detail=f"community {SENSITIVE_MARKER} invalida",
            )
        )

        self.assertFalse(result["sucesso"])
        self.assertEqual(result["erro_codigo"], "snmp_community_invalida")

    def test_classificacao_geral_verde_quando_so_houver_green(self):
        result, _, _ = self.collect(walk_result=snmp_success([raw_alert("Em espera")]))

        self.assertEqual(result["classificacao_geral"], "verde")

    def test_classificacao_geral_amarela_quando_houver_low_ou_medium(self):
        result, _, _ = self.collect(walk_result=snmp_success([raw_alert("Toner baixo")]))

        self.assertEqual(result["classificacao_geral"], "amarelo")

    def test_classificacao_geral_vermelha_quando_houver_high(self):
        result, _, _ = self.collect(
            walk_result=snmp_success([raw_alert("Substituir toner")])
        )

        self.assertEqual(result["classificacao_geral"], "vermelho")

    def test_classificacao_geral_cinza_quando_so_houver_unknown(self):
        result, _, _ = self.collect(
            walk_result=snmp_success([raw_alert("Mensagem nao catalogada")])
        )

        self.assertEqual(result["classificacao_geral"], "cinza")

    def test_classificacao_geral_cinza_quando_houver_verde_e_unknown(self):
        result, _, _ = self.collect(
            walk_result=snmp_success(
                [raw_alert("Em espera"), raw_alert("Mensagem nao catalogada")]
            )
        )

        self.assertEqual(result["classificacao_geral"], "cinza")

    def test_classificacao_geral_amarela_quando_houver_amarelo_e_unknown(self):
        result, _, _ = self.collect(
            walk_result=snmp_success(
                [raw_alert("Toner baixo"), raw_alert("Mensagem nao catalogada")]
            )
        )

        self.assertEqual(result["classificacao_geral"], "amarelo")

    def test_classificacao_geral_vermelha_quando_houver_vermelho_e_unknown(self):
        result, _, _ = self.collect(
            walk_result=snmp_success(
                [raw_alert("Substituir toner"), raw_alert("Mensagem nao catalogada")]
            )
        )

        self.assertEqual(result["classificacao_geral"], "vermelho")

    def test_community_snmp_nao_aparece_no_retorno(self):
        result, _, _ = self.collect(
            walk_result=snmp_success([raw_alert("Substituir toner")])
        )

        self.assertNotIn(SENSITIVE_MARKER, str(result))

    def test_community_snmp_nao_aparece_em_erros_serializados(self):
        result, _, _ = self.collect(
            walk_result=snmp_failure(
                error_code="snmp_sem_resposta",
                error_detail=f"sem resposta usando {SENSITIVE_MARKER}",
            )
        )

        self.assertFalse(result["sucesso"])
        self.assertNotIn(SENSITIVE_MARKER, str(result))
        self.assertIn("[community_oculta]", result["erro_detalhe"])

    def test_oid_retornado_pelo_walk_e_preservado_em_cada_alerta_bruto(self):
        result, _, _ = self.collect(
            walk_result=snmp_success([raw_alert("Substituir toner", oid=f"{ALERT_BASE_OID}.1.8")])
        )

        self.assertEqual(result["alertas_brutos"][0]["oid_retornado"], f"{ALERT_BASE_OID}.1.8")

    def test_oid_configurado_e_preservado_no_resultado_geral(self):
        result, _, _ = self.collect(walk_result=snmp_success([raw_alert("Em espera")]))

        self.assertEqual(result["oid_configurado"], ALERT_BASE_OID)

    def test_valor_repr_e_preservado(self):
        result, _, _ = self.collect(
            walk_result=snmp_success(
                [raw_alert("Substituir toner", value_repr="OctetString('Substituir toner')")]
            )
        )

        self.assertEqual(
            result["alertas_brutos"][0]["valor_repr"],
            "OctetString('Substituir toner')",
        )

    def test_service_nao_cria_registros_em_alertas_impressoras(self):
        self.collect(walk_result=snmp_success([raw_alert("Substituir toner")]))

        self.assertFalse(inspect(self.engine).has_table("alertas_impressoras"))

    def test_service_nao_cria_registros_em_historico_alertas_impressoras(self):
        self.collect(walk_result=snmp_success([raw_alert("Substituir toner")]))

        self.assertFalse(inspect(self.engine).has_table("historico_alertas_impressoras"))
