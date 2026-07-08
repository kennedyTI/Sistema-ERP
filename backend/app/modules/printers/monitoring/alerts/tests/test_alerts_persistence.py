import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import django
from django.apps import apps
from django.contrib.admin.sites import AdminSite
from sqlalchemy import CheckConstraint, UniqueConstraint, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backoffice.settings")
if not apps.ready:
    django.setup()

from backend.app.modules.printers.machines.models import (  # noqa: E402
    PrinterMachine,
    PrinterModel,
)
from backend.app.modules.printers.monitoring.alerts.admin import (  # noqa: E402
    PrinterAlertHistoryAdmin,
    PrinterCurrentAlertAdmin,
)
from backend.app.modules.printers.monitoring.alerts.django_models import (  # noqa: E402
    PrinterAlertHistoryAdminModel,
    PrinterCurrentAlertAdminModel,
)
from backend.app.modules.printers.monitoring.alerts.models import (  # noqa: E402
    AlertaImpressora,
    HistoricoAlertaImpressora,
)
from backend.app.modules.printers.monitoring.alerts.services import (  # noqa: E402
    collect_and_sync_machine_alerts,
    sync_machine_alerts_from_collection_result,
)
from backend.app.modules.printers.monitoring.config import (  # noqa: E402
    MonitoringSettings,
)
from backend.app.modules.printers.monitoring.snmp.models import (  # noqa: E402
    PrinterSnmpOid,
)
from backend.app.modules.printers.monitoring.state.models import (  # noqa: E402
    PrinterAlertRule,
)
from backend.app.modules.printers.monitoring.state.django_models import (  # noqa: E402
    PrinterAlertRuleAdminModel,
)
from backend.app.modules.printers.monitoring.state.seed import (  # noqa: E402
    INITIAL_ALERT_RULES,
    seed_alert_rules,
)


ALERT_BASE_OID = "1.3.6.1.2.1.43.18.1.1.8"
SENSITIVE_MARKER = "community-real-nao-pode-vazar"


class PermissionUserStub:
    is_active = True
    is_staff = True
    is_authenticated = True

    def __init__(self, permissions=()):
        self.permissions = set(permissions)

    def has_perm(self, permission):
        return permission in self.permissions


class RequestStub:
    GET = {}

    def __init__(self, user):
        self.user = user


class FakeRedis:
    def __init__(self):
        self.values = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def eval(self, script, key_count, key, token):
        if self.values.get(key) == token:
            del self.values[key]
            return 1
        return 0


class SequenceCollector:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        index = min(len(self.calls) - 1, len(self.results) - 1)
        return dict(self.results[index])


def raw_alert(message, *, oid=f"{ALERT_BASE_OID}.1.1"):
    return {
        "oid_retornado": oid,
        "valor_original": message,
        "valor_repr": repr(message),
        "tipo_snmp": "OctetString",
    }


def normalized_alert(code, *, severity, classification, recognized=True):
    return {
        "codigo": code,
        "severidade": severity,
        "classificacao": classification,
        "reconhecido": recognized,
    }


def alert_result(machine_id, raw_alerts, normalized_alerts, *, mode="walk"):
    return {
        "maquina_id": machine_id,
        "sucesso": True,
        "alertas_brutos": raw_alerts,
        "alertas_normalizados": normalized_alerts,
        "classificacao_geral": "verde",
        "origem_coleta": "snmp",
        "modo_consulta": mode,
        "oid_configurado": ALERT_BASE_OID,
    }


def snmp_empty_result(machine_id):
    return {
        "maquina_id": machine_id,
        "sucesso": True,
        "alertas_brutos": [],
        "alertas_normalizados": [
            {
                "codigo": "sem_alerta",
                "severidade": "unknown",
                "classificacao": "cinza",
                "descricao": "Sem alerta",
                "mensagem_original": None,
                "reconhecido": False,
                "persistir": False,
            }
        ],
        "classificacao_geral": "cinza",
        "origem_coleta": "snmp",
        "modo_consulta": "walk",
        "chave_metrica": "alert_raw",
        "oid_configurado": ALERT_BASE_OID,
        "sem_alerta_real": True,
    }


def html_alert_result(machine_id, raw_alerts, normalized_alerts):
    return {
        "maquina_id": machine_id,
        "sucesso": True,
        "alertas_brutos": raw_alerts,
        "alertas_normalizados": normalized_alerts,
        "classificacao_geral": "amarelo",
        "origem_coleta": "html",
        "modo_consulta": "html_autenticado",
        "chave_metrica": "html_status",
        "oid_configurado": None,
        "sem_alerta_real": False,
    }


def ipp_alert_result(machine_id, raw_alerts, normalized_alerts):
    return {
        "maquina_id": machine_id,
        "sucesso": True,
        "alertas_brutos": raw_alerts,
        "alertas_normalizados": normalized_alerts,
        "classificacao_geral": "verde",
        "origem_coleta": "ipp",
        "modo_consulta": "ipp",
        "chave_metrica": "ipp_status",
        "oid_configurado": None,
        "sem_alerta_real": False,
    }


def snmp_failure(machine_id, *, code="snmp_timeout", detail="Tempo limite SNMP."):
    return {
        "maquina_id": machine_id,
        "sucesso": False,
        "erro_codigo": code,
        "erro_detalhe": detail,
    }


class AlertsPersistenceSchemaTest(TestCase):
    def test_models_definem_tabelas_campos_constraints_e_valores_controlados(self):
        self.assertEqual(AlertaImpressora.__tablename__, "alertas_impressoras")
        self.assertEqual(
            HistoricoAlertaImpressora.__tablename__,
            "historico_alertas_impressoras",
        )
        self.assertNotEqual(AlertaImpressora.__tablename__, "tentativas_coleta_impressoras")

        current_columns = AlertaImpressora.__table__.c
        history_columns = HistoricoAlertaImpressora.__table__.c

        self.assertFalse(current_columns.regra_alerta_id.nullable)
        self.assertTrue(current_columns.oid_snmp_id.nullable)
        self.assertIn("codigo_alerta", history_columns)
        self.assertIn("detalhes", history_columns)

        unique_constraints = [
            constraint
            for constraint in AlertaImpressora.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        ]
        self.assertTrue(
            any(
                constraint.name == "uq_alertas_impressoras_maquina_chave"
                and {column.name for column in constraint.columns}
                == {"maquina_id", "chave_alerta"}
                for constraint in unique_constraints
            )
        )

        check_text = " ".join(
            str(constraint.sqltext)
            for constraint in (
                list(AlertaImpressora.__table__.constraints)
                + list(HistoricoAlertaImpressora.__table__.constraints)
            )
            if isinstance(constraint, CheckConstraint)
        )
        for value in ("snmp", "html", "ipp", "sistema"):
            self.assertIn(value, check_text)
        for value in ("get", "walk", "html_autenticado", "ipp", "cascata"):
            self.assertIn(value, check_text)
        for value in ("snmp_get", "snmp_walk", "html_autenticado", "ipp", "falha_cascata"):
            self.assertIn(value, check_text)

    def test_migration_cria_tabelas_e_nao_cria_tentativas(self):
        migration_path = Path(
            "backend/app/migrations/versions/20260617_printer_alerts_persistence.py"
        )
        content = migration_path.read_text(encoding="utf-8")

        self.assertIn('"alertas_impressoras"', content)
        self.assertIn('"historico_alertas_impressoras"', content)
        self.assertIn("uq_alertas_impressoras_maquina_chave", content)
        self.assertNotIn("tentativas_coleta_impressoras", content)

    def test_seed_garante_regras_tecnicas(self):
        rules = {rule["codigo"]: rule for rule in INITIAL_ALERT_RULES}

        self.assertEqual(rules["unknown"]["severidade"], "unknown")
        self.assertEqual(rules["sem_retorno_alerta"]["severidade"], "unknown")
        self.assertEqual(rules["falha_coleta_alertas"]["severidade"], "high")


class AlertsAdminTest(TestCase):
    def test_admin_alertas_atuais_e_somente_leitura_no_grupo_alertas(self):
        model_admin = PrinterCurrentAlertAdmin(PrinterCurrentAlertAdminModel, AdminSite())
        request = RequestStub(
            PermissionUserStub({"printer_alert_rules.view_printercurrentalertadminmodel"})
        )

        self.assertEqual(PrinterCurrentAlertAdminModel._meta.app_label, "printer_alert_rules")
        self.assertEqual(
            PrinterCurrentAlertAdminModel._meta.verbose_name_plural,
            "alertas_impressoras",
        )
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertTrue(model_admin.has_view_permission(request))
        self.assertIn("regra_alerta_resumida", model_admin.list_display)

        obj = PrinterCurrentAlertAdminModel()
        obj.regra_alerta = PrinterAlertRuleAdminModel(id=13, codigo="idle")
        self.assertEqual(model_admin.regra_alerta_resumida(obj), "#13 - idle")

    def test_admin_historico_e_somente_leitura_no_grupo_alertas(self):
        model_admin = PrinterAlertHistoryAdmin(
            PrinterAlertHistoryAdminModel,
            AdminSite(),
        )
        request = RequestStub(
            PermissionUserStub({"printer_alert_rules.view_printeralerthistoryadminmodel"})
        )

        self.assertEqual(PrinterAlertHistoryAdminModel._meta.app_label, "printer_alert_rules")
        self.assertEqual(
            PrinterAlertHistoryAdminModel._meta.verbose_name_plural,
            "historico_alertas_impressoras",
        )
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertTrue(model_admin.has_view_permission(request))
        self.assertIn("regra_alerta_resumida", model_admin.list_display)

        obj = PrinterAlertHistoryAdminModel(regra_alerta_id=13, codigo_alerta="idle")
        self.assertEqual(model_admin.regra_alerta_resumida(obj), "#13 - idle")

    def test_admin_historico_aceita_json_ja_desserializado_pelo_driver(self):
        field = PrinterAlertHistoryAdminModel._meta.get_field("detalhes")
        value = {"quantidade_alertas": 1}

        self.assertEqual(field.from_db_value(value, None, None), value)
        self.assertEqual(
            field.from_db_value('{"quantidade_alertas": 1}', None, None),
            value,
        )


class AlertsPersistenceServiceTest(TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        PrinterModel.__table__.create(self.engine)
        PrinterMachine.__table__.create(self.engine)
        PrinterSnmpOid.__table__.create(self.engine)
        PrinterAlertRule.__table__.create(self.engine)
        AlertaImpressora.__table__.create(self.engine)
        HistoricoAlertaImpressora.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        seed_alert_rules(self.db)
        self.model = self.add_model(name="Modelo A")
        self.machine = self.add_machine(model=self.model, ip="192.0.2.10")
        self.oid = self.add_oid(self.model, mode="walk")

    def tearDown(self):
        self.db.close()

    def add_model(self, *, name, manufacturer="Fabricante"):
        model = PrinterModel(manufacturer=manufacturer, name=name)
        self.db.add(model)
        self.db.commit()
        return model

    def add_machine(self, *, model, ip):
        machine = PrinterMachine(
            name=f"Impressora {ip}",
            ip_address=ip,
            printer_model=model,
            is_active=True,
        )
        self.db.add(machine)
        self.db.commit()
        return machine

    def add_oid(self, model, *, mode):
        oid = PrinterSnmpOid(
            modelo_id=model.id,
            chave_metrica="alert_raw",
            oid=ALERT_BASE_OID,
            tipo_valor="string",
            versao_snmp="2c",
            modo_consulta=mode,
            ativo=True,
        )
        self.db.add(oid)
        self.db.commit()
        return oid

    def current_alerts(self, machine=None):
        return (
            self.db.query(AlertaImpressora)
            .filter(AlertaImpressora.maquina_id == (machine or self.machine).id)
            .order_by(AlertaImpressora.chave_alerta.asc())
            .all()
        )

    def histories(self, machine=None):
        return (
            self.db.query(HistoricoAlertaImpressora)
            .filter(HistoricoAlertaImpressora.maquina_id == (machine or self.machine).id)
            .order_by(HistoricoAlertaImpressora.id.asc())
            .all()
        )

    def rule_code_for_current(self, row):
        return self.db.get(PrinterAlertRule, row.regra_alerta_id).codigo

    def sync(self, raw_alerts, normalized_alerts, *, mode="walk"):
        return sync_machine_alerts_from_collection_result(
            self.db,
            collection_result=alert_result(
                self.machine.id,
                raw_alerts,
                normalized_alerts,
                mode=mode,
            ),
        )

    def test_sincroniza_um_alerta_com_historico_inicial_vermelho(self):
        result = self.sync(
            [raw_alert("Substituir toner")],
            [normalized_alert("replace_toner", severity="high", classification="vermelho")],
        )
        current = self.current_alerts()
        histories = self.histories()

        self.assertTrue(result["sincronizado"])
        self.assertEqual(len(current), 1)
        self.assertEqual(self.rule_code_for_current(current[0]), "replace_toner")
        self.assertEqual(current[0].origem_coleta, "snmp")
        self.assertEqual(current[0].metodo_confirmacao, "snmp_walk")
        self.assertEqual(current[0].oid_snmp_id, self.oid.id)
        self.assertEqual(len(histories), 1)
        self.assertEqual(histories[0].codigo_evento, "estado_inicial_alerta")
        self.assertEqual(histories[0].codigo_alerta, "replace_toner")
        self.assertEqual(histories[0].severidade, "high")
        self.assertTrue(histories[0].descricao_evento)
        self.assertEqual(histories[0].detalhes["quantidade_alertas"], 1)

    def test_sincroniza_multiplos_alertas(self):
        self.sync(
            [
                raw_alert("Toner baixo", oid=f"{ALERT_BASE_OID}.1.1"),
                raw_alert("Substituir toner", oid=f"{ALERT_BASE_OID}.1.2"),
            ],
            [
                normalized_alert("toner_low", severity="medium", classification="amarelo"),
                normalized_alert("replace_toner", severity="high", classification="vermelho"),
            ],
        )

        current = self.current_alerts()
        self.assertEqual(len(current), 2)
        self.assertEqual(
            {self.rule_code_for_current(row) for row in current},
            {"toner_low", "replace_toner"},
        )

    def test_atualiza_alerta_existente_sem_duplicar(self):
        alert = raw_alert("Toner baixo")
        normalized = normalized_alert(
            "toner_low",
            severity="medium",
            classification="amarelo",
        )

        self.sync([alert], [normalized])
        self.sync([raw_alert("Toner baixo atualizado")], [normalized])

        current = self.current_alerts()
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0].mensagem_original, "Toner baixo atualizado")

    def test_remove_alerta_antigo_que_nao_veio_na_coleta(self):
        self.sync(
            [
                raw_alert("Toner baixo", oid=f"{ALERT_BASE_OID}.1.1"),
                raw_alert("Substituir toner", oid=f"{ALERT_BASE_OID}.1.2"),
            ],
            [
                normalized_alert("toner_low", severity="medium", classification="amarelo"),
                normalized_alert("replace_toner", severity="high", classification="vermelho"),
            ],
        )
        self.sync(
            [raw_alert("Toner baixo", oid=f"{ALERT_BASE_OID}.1.1")],
            [normalized_alert("toner_low", severity="medium", classification="amarelo")],
        )

        current = self.current_alerts()
        self.assertEqual(len(current), 1)
        self.assertEqual(self.rule_code_for_current(current[0]), "toner_low")

    def test_coleta_vazia_limpa_alertas_atuais_sem_persistir_sem_alerta(self):
        self.sync(
            [raw_alert("Substituir toner")],
            [normalized_alert("replace_toner", severity="high", classification="vermelho")],
        )

        result = self.sync([], [])
        current = self.current_alerts()
        histories = self.histories()

        self.assertEqual(result["classificacao_nova"], "cinza")
        self.assertEqual(result["alertas_atuais"], 0)
        self.assertTrue(result["sem_alerta_real"])
        self.assertEqual(len(current), 0)
        self.assertEqual(len(histories), 1)
        self.assertEqual(histories[0].codigo_evento, "estado_inicial_alerta")
        self.assertEqual(histories[0].classificacao_nova, "vermelho")

    def test_falha_snmp_apos_duas_tentativas_vira_falha_consolidada_vermelha(self):
        collector = SequenceCollector(
            snmp_failure(self.machine.id),
            snmp_failure(self.machine.id),
        )

        result = collect_and_sync_machine_alerts(
            self.db,
            machine_id=self.machine.id,
            redis_client=FakeRedis(),
            settings=MonitoringSettings(snmp_community=SENSITIVE_MARKER),
            collector=collector,
        )

        current = self.current_alerts()
        self.assertTrue(result["processada"])
        self.assertEqual(result["tentativas_snmp"], 2)
        self.assertEqual(result["classificacao_nova"], "vermelho")
        self.assertEqual(self.rule_code_for_current(current[0]), "falha_coleta_alertas")
        self.assertEqual(current[0].origem_coleta, "sistema")
        self.assertEqual(current[0].metodo_confirmacao, "falha_cascata")

    def test_canon_com_snmp_vazio_usa_html_autenticado_como_fallback(self):
        canon_model = self.add_model(manufacturer="Canon", name="IR-C3326I")
        canon_machine = self.add_machine(model=canon_model, ip="192.0.2.30")
        self.add_oid(canon_model, mode="walk")
        html_collector = SequenceCollector(
            html_alert_result(
                canon_machine.id,
                [raw_alert("O toner Magenta está baixo.", oid=None)],
                [
                    normalized_alert(
                        "toner_low",
                        severity="medium",
                        classification="amarelo",
                    )
                ],
            )
        )

        result = collect_and_sync_machine_alerts(
            self.db,
            machine_id=canon_machine.id,
            redis_client=FakeRedis(),
            settings=MonitoringSettings(snmp_community=SENSITIVE_MARKER),
            collector=SequenceCollector(snmp_empty_result(canon_machine.id)),
            html_collector=html_collector,
        )

        current = self.current_alerts(canon_machine)
        self.assertTrue(result["processada"])
        self.assertTrue(result["fallback_html_usado"])
        self.assertEqual(len(html_collector.calls), 1)
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0].origem_coleta, "html")
        self.assertEqual(current[0].metodo_coleta, "html_autenticado")
        self.assertEqual(current[0].metodo_confirmacao, "html_autenticado")
        self.assertIsNone(current[0].oid_snmp_id)
        self.assertTrue(current[0].chave_alerta.startswith("html:html_autenticado:"))

    def test_canon_com_alert_raw_snmp_nao_aciona_html(self):
        canon_model = self.add_model(manufacturer="Canon", name="IR-C3326I")
        canon_machine = self.add_machine(model=canon_model, ip="192.0.2.31")
        self.add_oid(canon_model, mode="walk")
        html_collector = SequenceCollector(
            html_alert_result(
                canon_machine.id,
                [raw_alert("O toner Magenta está baixo.", oid=None)],
                [
                    normalized_alert(
                        "toner_low",
                        severity="medium",
                        classification="amarelo",
                    )
                ],
            )
        )

        result = collect_and_sync_machine_alerts(
            self.db,
            machine_id=canon_machine.id,
            redis_client=FakeRedis(),
            settings=MonitoringSettings(snmp_community=SENSITIVE_MARKER),
            collector=SequenceCollector(
                alert_result(
                    canon_machine.id,
                    [raw_alert("Substituir toner")],
                    [
                        normalized_alert(
                            "replace_toner",
                            severity="high",
                            classification="vermelho",
                        )
                    ],
                )
            ),
            html_collector=html_collector,
        )

        current = self.current_alerts(canon_machine)
        self.assertFalse(result["fallback_html_usado"])
        self.assertEqual(len(html_collector.calls), 0)
        self.assertEqual(current[0].origem_coleta, "snmp")
        self.assertEqual(current[0].metodo_confirmacao, "snmp_walk")

    def test_canon_com_falha_snmp_usa_html_autenticado_como_fallback(self):
        canon_model = self.add_model(manufacturer="Canon", name="IR-C3326I")
        canon_machine = self.add_machine(model=canon_model, ip="192.0.2.32")
        self.add_oid(canon_model, mode="walk")
        html_collector = SequenceCollector(
            html_alert_result(
                canon_machine.id,
                [raw_alert("O toner Amarelo está baixo.", oid=None)],
                [
                    normalized_alert(
                        "toner_low",
                        severity="medium",
                        classification="amarelo",
                    )
                ],
            )
        )

        result = collect_and_sync_machine_alerts(
            self.db,
            machine_id=canon_machine.id,
            redis_client=FakeRedis(),
            settings=MonitoringSettings(snmp_community=SENSITIVE_MARKER),
            collector=SequenceCollector(
                snmp_failure(canon_machine.id),
                snmp_failure(canon_machine.id),
            ),
            html_collector=html_collector,
        )

        current = self.current_alerts(canon_machine)
        self.assertTrue(result["processada"])
        self.assertEqual(result["tentativas_snmp"], 2)
        self.assertTrue(result["fallback_html_usado"])
        self.assertEqual(len(html_collector.calls), 1)
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0].origem_coleta, "html")
        self.assertEqual(current[0].metodo_confirmacao, "html_autenticado")
        self.assertEqual(self.rule_code_for_current(current[0]), "toner_low")

    def test_brother_l2540dw_completa_alerta_snmp_com_status_html(self):
        brother_model = self.add_model(manufacturer="Brother", name="DCP-L2540DW")
        brother_machine = self.add_machine(model=brother_model, ip="192.0.2.33")
        self.add_oid(brother_model, mode="walk")
        html_collector = SequenceCollector(
            html_alert_result(
                brother_machine.id,
                [
                    raw_alert("Trocar Cilindro", oid=None),
                    raw_alert("Subs. toner", oid=None),
                    raw_alert("Sleep", oid=None),
                ],
                [
                    normalized_alert(
                        "replace_drum",
                        severity="high",
                        classification="vermelho",
                    ),
                    normalized_alert(
                        "replace_toner",
                        severity="high",
                        classification="vermelho",
                    ),
                    normalized_alert(
                        "sleep",
                        severity="green",
                        classification="verde",
                    ),
                ],
            )
        )

        result = collect_and_sync_machine_alerts(
            self.db,
            machine_id=brother_machine.id,
            redis_client=FakeRedis(),
            settings=MonitoringSettings(snmp_community=SENSITIVE_MARKER),
            collector=SequenceCollector(
                alert_result(
                    brother_machine.id,
                    [raw_alert("Trocar Cilindro")],
                    [
                        normalized_alert(
                            "replace_drum",
                            severity="high",
                            classification="vermelho",
                        )
                    ],
                )
            ),
            html_collector=html_collector,
        )

        current = self.current_alerts(brother_machine)
        self.assertTrue(result["fallback_html_usado"])
        self.assertEqual(len(html_collector.calls), 1)
        self.assertEqual(len(current), 3)
        self.assertEqual(
            {self.rule_code_for_current(row) for row in current},
            {"replace_drum", "replace_toner", "sleep"},
        )
        self.assertTrue(all(row.origem_coleta == "html" for row in current))
        self.assertTrue(
            all(row.metodo_confirmacao == "html_autenticado" for row in current)
        )

    def test_modelo_nao_canon_com_snmp_vazio_nao_aciona_html(self):
        html_collector = SequenceCollector(
            html_alert_result(
                self.machine.id,
                [raw_alert("O toner Magenta está baixo.", oid=None)],
                [
                    normalized_alert(
                        "toner_low",
                        severity="medium",
                        classification="amarelo",
                    )
                ],
            )
        )

        result = collect_and_sync_machine_alerts(
            self.db,
            machine_id=self.machine.id,
            redis_client=FakeRedis(),
            settings=MonitoringSettings(snmp_community=SENSITIVE_MARKER),
            collector=SequenceCollector(snmp_empty_result(self.machine.id)),
            html_collector=html_collector,
        )

        self.assertFalse(result["fallback_html_usado"])
        self.assertEqual(len(html_collector.calls), 0)
        self.assertEqual(len(self.current_alerts()), 0)

    def test_hp_mfp_4303_com_snmp_vazio_usa_ipp_como_fallback(self):
        hp_model = self.add_model(manufacturer="HP", name="MFP-4303")
        hp_machine = self.add_machine(model=hp_model, ip="192.0.2.40")
        self.add_oid(hp_model, mode="walk")
        ipp_collector = SequenceCollector(
            ipp_alert_result(
                hp_machine.id,
                [raw_alert("Em espera", oid=None)],
                [normalized_alert("idle", severity="green", classification="verde")],
            )
        )

        result = collect_and_sync_machine_alerts(
            self.db,
            machine_id=hp_machine.id,
            redis_client=FakeRedis(),
            settings=MonitoringSettings(snmp_community=SENSITIVE_MARKER),
            collector=SequenceCollector(snmp_empty_result(hp_machine.id)),
            ipp_collector=ipp_collector,
        )

        current = self.current_alerts(hp_machine)
        self.assertTrue(result["fallback_ipp_usado"])
        self.assertFalse(result["fallback_html_usado"])
        self.assertEqual(len(ipp_collector.calls), 1)
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0].origem_coleta, "ipp")
        self.assertEqual(current[0].metodo_coleta, "ipp")
        self.assertEqual(current[0].metodo_confirmacao, "ipp")
        self.assertEqual(self.rule_code_for_current(current[0]), "idle")

    def test_hp_mfp_4303_com_alerta_snmp_nao_aciona_ipp(self):
        hp_model = self.add_model(manufacturer="HP", name="MFP-4303")
        hp_machine = self.add_machine(model=hp_model, ip="192.0.2.41")
        self.add_oid(hp_model, mode="walk")
        ipp_collector = SequenceCollector(
            ipp_alert_result(
                hp_machine.id,
                [raw_alert("Em espera", oid=None)],
                [normalized_alert("idle", severity="green", classification="verde")],
            )
        )

        result = collect_and_sync_machine_alerts(
            self.db,
            machine_id=hp_machine.id,
            redis_client=FakeRedis(),
            settings=MonitoringSettings(snmp_community=SENSITIVE_MARKER),
            collector=SequenceCollector(
                alert_result(
                    hp_machine.id,
                    [raw_alert("Toner baixo")],
                    [normalized_alert("toner_low", severity="medium", classification="amarelo")],
                )
            ),
            ipp_collector=ipp_collector,
        )

        self.assertFalse(result["fallback_ipp_usado"])
        self.assertEqual(len(ipp_collector.calls), 0)
        self.assertEqual(self.current_alerts(hp_machine)[0].origem_coleta, "snmp")

    def test_nao_registra_historico_quando_classificacao_nao_muda(self):
        alert = [raw_alert("Toner baixo")]
        normalized = [normalized_alert("toner_low", severity="medium", classification="amarelo")]
        self.sync(alert, normalized)
        self.sync(alert, normalized)

        self.assertEqual(len(self.histories()), 1)

    def test_registra_classificacao_alterada_quando_muda(self):
        self.sync(
            [raw_alert("Toner baixo")],
            [normalized_alert("toner_low", severity="medium", classification="amarelo")],
        )
        self.sync(
            [raw_alert("Substituir toner")],
            [normalized_alert("replace_toner", severity="high", classification="vermelho")],
        )

        histories = self.histories()
        self.assertEqual(histories[-1].codigo_evento, "classificacao_alterada")
        self.assertEqual(histories[-1].classificacao_anterior, "amarelo")
        self.assertEqual(histories[-1].classificacao_nova, "vermelho")

    def test_historico_usa_alerta_que_define_nova_classificacao(self):
        self.sync(
            [raw_alert("Sleep")],
            [normalized_alert("sleep", severity="green", classification="verde")],
        )
        self.sync(
            [
                raw_alert("Sleep", oid=f"{ALERT_BASE_OID}.1.1"),
                raw_alert("Trocar Cilindro", oid=f"{ALERT_BASE_OID}.1.2"),
            ],
            [
                normalized_alert("sleep", severity="green", classification="verde"),
                normalized_alert("replace_drum", severity="high", classification="vermelho"),
            ],
        )

        history = self.histories()[-1]
        self.assertEqual(history.codigo_evento, "classificacao_alterada")
        self.assertEqual(history.codigo_alerta, "replace_drum")
        self.assertEqual(history.severidade, "high")
        self.assertEqual(history.mensagem_original, "Trocar Cilindro")
        self.assertEqual(history.classificacao_anterior, "verde")
        self.assertEqual(history.classificacao_nova, "vermelho")

    def test_nao_registra_troca_entre_estados_verdes(self):
        self.sync(
            [raw_alert("Em espera")],
            [normalized_alert("idle", severity="green", classification="verde")],
        )
        self.sync(
            [raw_alert("Dormindo")],
            [normalized_alert("sleep", severity="green", classification="verde")],
        )

        self.assertEqual(len(self.histories()), 0)

    def test_nao_registra_transicoes_equivalentes_do_grupo_normal(self):
        transitions = (
            ("Estado normal", "ok", "Em espera", "idle"),
            ("Estado normal", "ok", "Dormindo", "sleep"),
            ("Sleep", "sleep", "Ready", "ok"),
            ("Pronto", "ok", "Imprimindo", "ok"),
            ("Imprimindo", "ok", "Em espera", "idle"),
            ("Idle", "idle", "Sleep", "sleep"),
        )

        for previous_message, previous_code, current_message, current_code in transitions:
            with self.subTest(previous=previous_message, current=current_message):
                self.sync(
                    [raw_alert(previous_message)],
                    [
                        normalized_alert(
                            previous_code,
                            severity="green",
                            classification="verde",
                        )
                    ],
                )
                self.sync(
                    [raw_alert(current_message)],
                    [
                        normalized_alert(
                            current_code,
                            severity="green",
                            classification="verde",
                        )
                    ],
                )

        self.assertEqual(len(self.histories()), 0)

    def test_registra_transicao_de_green_para_medium(self):
        self.sync(
            [raw_alert("Estado normal")],
            [normalized_alert("ok", severity="green", classification="verde")],
        )
        self.sync(
            [raw_alert("Toner baixo")],
            [normalized_alert("toner_low", severity="medium", classification="amarelo")],
        )

        history = self.histories()[-1]
        self.assertEqual(history.classificacao_anterior, "verde")
        self.assertEqual(history.classificacao_nova, "amarelo")

    def test_registra_substituir_toner_para_toner_baixo(self):
        self.sync(
            [raw_alert("Substituir toner")],
            [normalized_alert("replace_toner", severity="high", classification="vermelho")],
        )
        self.sync(
            [raw_alert("Toner baixo")],
            [normalized_alert("toner_low", severity="medium", classification="amarelo")],
        )

        history = self.histories()[-1]
        self.assertEqual(history.classificacao_anterior, "vermelho")
        self.assertEqual(history.classificacao_nova, "amarelo")

    def test_registra_retorno_de_vermelho_para_verde(self):
        self.sync(
            [raw_alert("Trocar Cilindro")],
            [normalized_alert("replace_drum", severity="high", classification="vermelho")],
        )
        self.sync(
            [raw_alert("Dormindo")],
            [normalized_alert("sleep", severity="green", classification="verde")],
        )

        histories = self.histories()
        self.assertEqual(len(histories), 2)
        self.assertEqual(histories[0].codigo_alerta, "replace_drum")
        self.assertEqual(histories[0].classificacao_nova, "vermelho")
        self.assertEqual(histories[1].codigo_alerta, "sleep")
        self.assertEqual(histories[1].classificacao_anterior, "vermelho")
        self.assertEqual(histories[1].classificacao_nova, "verde")

    def test_registra_retorno_de_amarelo_para_verde(self):
        self.sync(
            [raw_alert("Toner baixo")],
            [normalized_alert("toner_low", severity="medium", classification="amarelo")],
        )
        self.sync(
            [raw_alert("Pronto")],
            [normalized_alert("ok", severity="green", classification="verde")],
        )

        histories = self.histories()
        self.assertEqual(len(histories), 2)
        self.assertEqual(histories[1].codigo_alerta, "ok")
        self.assertEqual(histories[1].classificacao_anterior, "amarelo")
        self.assertEqual(histories[1].classificacao_nova, "verde")

    def test_nao_registra_primeira_coleta_verde(self):
        self.sync(
            [raw_alert("Em espera")],
            [normalized_alert("idle", severity="green", classification="verde")],
        )

        self.assertEqual(len(self.histories()), 0)

    def test_registra_estado_inicial_amarelo(self):
        self.sync(
            [raw_alert("Toner baixo")],
            [normalized_alert("toner_low", severity="medium", classification="amarelo")],
        )

        self.assertEqual(self.histories()[0].codigo_evento, "estado_inicial_alerta")
        self.assertEqual(self.histories()[0].classificacao_nova, "amarelo")

    def test_registra_estado_inicial_vermelho(self):
        self.sync(
            [raw_alert("Substituir toner")],
            [normalized_alert("replace_toner", severity="high", classification="vermelho")],
        )

        self.assertEqual(self.histories()[0].codigo_evento, "estado_inicial_alerta")
        self.assertEqual(self.histories()[0].classificacao_nova, "vermelho")

    def test_registra_estado_inicial_cinza(self):
        self.sync(
            [raw_alert("Mensagem nova")],
            [
                normalized_alert(
                    "unknown",
                    severity="unknown",
                    classification="cinza",
                    recognized=False,
                )
            ],
        )

        self.assertEqual(self.histories()[0].codigo_evento, "estado_inicial_alerta")
        self.assertEqual(self.histories()[0].classificacao_nova, "cinza")

    def test_unknown_novo_por_modelo_registra_evento_uma_vez(self):
        unknown = [
            raw_alert("Mensagem nao catalogada"),
        ]
        normalized = [
            normalized_alert(
                "unknown",
                severity="unknown",
                classification="cinza",
                recognized=False,
            )
        ]

        self.sync(unknown, normalized)
        self.sync(unknown, normalized)

        unknown_events = [
            row for row in self.histories() if row.codigo_evento == "alerta_nao_catalogado"
        ]
        self.assertEqual(len(unknown_events), 1)
        self.assertEqual(unknown_events[0].codigo_alerta, "unknown")
        self.assertEqual(unknown_events[0].severidade, "unknown")

    def test_unknown_mesma_mensagem_em_modelo_diferente_registra_novo_evento(self):
        unknown = [
            raw_alert("Mensagem nao catalogada"),
        ]
        normalized = [
            normalized_alert(
                "unknown",
                severity="unknown",
                classification="cinza",
                recognized=False,
            )
        ]
        self.sync(unknown, normalized)

        other_model = self.add_model(name="Modelo B")
        other_machine = self.add_machine(model=other_model, ip="192.0.2.20")
        self.add_oid(other_model, mode="walk")
        sync_machine_alerts_from_collection_result(
            self.db,
            collection_result=alert_result(other_machine.id, unknown, normalized),
        )

        unknown_events = (
            self.db.query(HistoricoAlertaImpressora)
            .filter(HistoricoAlertaImpressora.codigo_evento == "alerta_nao_catalogado")
            .all()
        )
        self.assertEqual(len(unknown_events), 2)

    def test_lock_por_maquina_bloqueia_sincronizacao_concorrente(self):
        redis_client = FakeRedis()
        redis_client.values[f"printers:lock:alerts:machine:{self.machine.id}"] = "ativo"

        result = collect_and_sync_machine_alerts(
            self.db,
            machine_id=self.machine.id,
            redis_client=redis_client,
            settings=MonitoringSettings(),
            collector=SequenceCollector(
                alert_result(
                    self.machine.id,
                    [raw_alert("Toner baixo")],
                    [
                        normalized_alert(
                            "toner_low",
                            severity="medium",
                            classification="amarelo",
                        )
                    ],
                )
            ),
        )

        self.assertFalse(result["processada"])
        self.assertEqual(result["motivo"], "lock_ativo")
        self.assertEqual(len(self.current_alerts()), 0)

    def test_falha_durante_sincronizacao_nao_deixa_estado_parcial(self):
        with patch.object(self.db, "commit", side_effect=RuntimeError("falha commit")):
            with self.assertRaises(RuntimeError):
                self.sync(
                    [raw_alert("Substituir toner")],
                    [
                        normalized_alert(
                            "replace_toner",
                            severity="high",
                            classification="vermelho",
                        )
                    ],
                )

        self.assertEqual(len(self.current_alerts()), 0)
        self.assertEqual(len(self.histories()), 0)

    def test_oid_walk_valido_deve_estar_dentro_da_base_configurada(self):
        self.sync(
            [raw_alert("Toner baixo", oid=f"{ALERT_BASE_OID}.1.99")],
            [normalized_alert("toner_low", severity="medium", classification="amarelo")],
        )

        current = self.current_alerts()[0]
        self.assertEqual(current.oid_retornado, f"{ALERT_BASE_OID}.1.99")
        self.assertEqual(self.rule_code_for_current(current), "toner_low")

    def test_oid_walk_fora_da_base_vira_falha_tecnica(self):
        self.sync(
            [raw_alert("Toner baixo", oid="1.3.6.1.4.1.999.1")],
            [normalized_alert("toner_low", severity="medium", classification="amarelo")],
        )

        current = self.current_alerts()[0]
        self.assertEqual(self.rule_code_for_current(current), "falha_coleta_alertas")
        self.assertEqual(current.oid_retornado, None)
        self.assertNotIn("Toner baixo", str(current.__dict__))

    def test_oid_get_deve_ser_igual_ao_oid_configurado(self):
        self.oid.modo_consulta = "get"
        self.db.commit()

        self.sync(
            [raw_alert("Em espera", oid=ALERT_BASE_OID)],
            [normalized_alert("idle", severity="green", classification="verde")],
            mode="get",
        )

        current = self.current_alerts()[0]
        self.assertEqual(current.metodo_confirmacao, "snmp_get")
        self.assertEqual(current.oid_retornado, ALERT_BASE_OID)

    def test_oid_get_diferente_vira_falha_tecnica(self):
        self.oid.modo_consulta = "get"
        self.db.commit()

        self.sync(
            [raw_alert("Em espera", oid=f"{ALERT_BASE_OID}.1")],
            [normalized_alert("idle", severity="green", classification="verde")],
            mode="get",
        )

        current = self.current_alerts()[0]
        self.assertEqual(self.rule_code_for_current(current), "falha_coleta_alertas")

    def test_community_nao_aparece_em_alertas_historico_ou_retorno_serializado(self):
        result = sync_machine_alerts_from_collection_result(
            self.db,
            collection_result=snmp_failure(
                self.machine.id,
                code="snmp_community_invalida",
                detail=f"community {SENSITIVE_MARKER} invalida",
            ),
        )
        current = self.current_alerts()
        histories = self.histories()

        self.assertNotIn(SENSITIVE_MARKER, str(result))
        self.assertNotIn(SENSITIVE_MARKER, str([row.__dict__ for row in current]))
        self.assertNotIn(SENSITIVE_MARKER, str([row.__dict__ for row in histories]))
