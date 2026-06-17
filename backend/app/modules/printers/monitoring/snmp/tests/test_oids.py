import os
from pathlib import Path
from unittest import TestCase

import django
from django.contrib.admin.sites import AdminSite
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backoffice.settings")
django.setup()

from backend.app.modules.printers.machines.models import PrinterModel  # noqa: E402
from backend.app.modules.printers.monitoring.snmp.admin import (  # noqa: E402
    PrinterSnmpOidAdmin,
)
from backend.app.modules.printers.monitoring.snmp.django_models import (  # noqa: E402
    PrinterSnmpOidAdminModel,
)
from backend.app.modules.printers.monitoring.snmp.models import (  # noqa: E402
    PrinterSnmpOid,
)
from backend.app.modules.printers.monitoring.snmp.oids import (  # noqa: E402
    get_active_oid_for_model,
    list_active_oids_for_model,
    oid_to_dict,
)
from backend.app.modules.printers.monitoring.snmp.seed import (  # noqa: E402
    INITIAL_SNMP_OIDS,
    INVALIDATED_SNMP_OIDS,
    PRT_ALERT_DESCRIPTION_BASE_OID,
    iter_seed_entries,
    seed_printer_snmp_oids,
)


APP_ROOT = Path(__file__).resolve().parents[5]
QUERY_MODE_MIGRATION = (
    APP_ROOT
    / "migrations"
    / "versions"
    / "20260617_printer_snmp_oids_query_mode.py"
)


def seed_entry(
    manufacturer: str = "Brother",
    model_name: str = "DCP-L1632W",
    metric_key: str = "alert_raw",
    oid: str = "1.3.6.1.2.1.43.18.1.1.8.1.1",
    value_type: str = "string",
    snmp_version: str = "2c",
    query_mode: str = "get",
) -> dict:
    return {
        "fabricante": manufacturer,
        "modelo": model_name,
        "chave_metrica": metric_key,
        "oid": oid,
        "tipo_valor": value_type,
        "versao_snmp": snmp_version,
        "modo_consulta": query_mode,
        "ativo": True,
    }


class PermissionUserStub:
    is_active = True
    is_staff = True
    is_authenticated = True

    def __init__(self, permissions=()):
        self.permissions = set(permissions)

    def has_perm(self, permission):
        return permission in self.permissions

    def get_username(self):
        return "usuario_teste"


class RequestStub:
    GET = {}

    def __init__(self, user):
        self.user = user


class PrinterSnmpOidSeedTest(TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        PrinterModel.__table__.create(engine)
        PrinterSnmpOid.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.models = []
        for item in INITIAL_SNMP_OIDS:
            model = PrinterModel(
                manufacturer=item["fabricante"],
                name=item["modelo"],
            )
            self.db.add(model)
            self.models.append(model)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _model(self, manufacturer: str, model_name: str) -> PrinterModel:
        for model in self.models:
            if model.manufacturer == manufacturer and model.name == model_name:
                return model
        raise AssertionError(f"Modelo nao encontrado no teste: {manufacturer} {model_name}")

    def _oid_row(
        self,
        manufacturer: str,
        model_name: str,
        metric_key: str,
    ) -> PrinterSnmpOid:
        model = self._model(manufacturer, model_name)
        return (
            self.db.query(PrinterSnmpOid)
            .filter_by(modelo_id=model.id, chave_metrica=metric_key)
            .one()
        )

    def test_migration_adiciona_modo_consulta_com_default_get(self):
        migration_text = QUERY_MODE_MIGRATION.read_text(encoding="utf-8")

        self.assertIn('down_revision = "20260616_snmp_oids"', migration_text)
        self.assertIn('"modo_consulta"', migration_text)
        self.assertIn('server_default="get"', migration_text)
        self.assertIn("ck_oids_snmp_impressoras_modo_consulta", migration_text)
        self.assertIn("modo_consulta IN ('get', 'walk')", migration_text)

    def test_modelo_declara_tabela_colunas_constraints_e_indices(self):
        self.assertEqual(
            PrinterSnmpOid.__tablename__,
            "oids_snmp_impressoras",
        )
        self.assertEqual(
            set(PrinterSnmpOid.__table__.columns.keys()),
            {
                "id",
                "modelo_id",
                "chave_metrica",
                "oid",
                "tipo_valor",
                "versao_snmp",
                "modo_consulta",
                "ativo",
                "criado_em",
                "atualizado_em",
            },
        )
        self.assertIn(
            "uq_oids_snmp_impressoras_modelo_metrica",
            {constraint.name for constraint in PrinterSnmpOid.__table__.constraints},
        )
        self.assertIn(
            "ck_oids_snmp_impressoras_modo_consulta",
            {constraint.name for constraint in PrinterSnmpOid.__table__.constraints},
        )
        self.assertFalse(PrinterSnmpOid.__table__.c.modo_consulta.nullable)
        self.assertEqual(PrinterSnmpOid.__table__.c.modo_consulta.default.arg, "get")
        self.assertEqual(
            {index.name for index in PrinterSnmpOid.__table__.indexes},
            {
                "ix_oids_snmp_impressoras_modelo_id",
                "ix_oids_snmp_impressoras_chave_metrica",
                "ix_oids_snmp_impressoras_ativo",
                "ix_oids_snmp_impressoras_modelo_metrica",
            },
        )

    def test_constraint_impede_duplicidade_por_modelo_e_metrica(self):
        first_model = self.models[0]
        self.db.add(
            PrinterSnmpOid(
                modelo_id=first_model.id,
                chave_metrica="alert_raw",
                oid="1.3.6.1.2.1.43.18.1.1.8.1.1",
                tipo_valor="string",
                versao_snmp="2c",
            )
        )
        self.db.add(
            PrinterSnmpOid(
                modelo_id=first_model.id,
                chave_metrica="alert_raw",
                oid="1.3.6.1.2.1.43.18.1.1.8.1.2",
                tipo_valor="string",
                versao_snmp="2c",
            )
        )

        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_modo_consulta_aceita_get_e_walk(self):
        first_model = self.models[0]
        self.db.add_all(
            [
                PrinterSnmpOid(
                    modelo_id=first_model.id,
                    chave_metrica="alert_raw",
                    oid="1.3.6.1.2.1.43.18.1.1.8.1.1",
                    tipo_valor="string",
                    versao_snmp="2c",
                    modo_consulta="get",
                ),
                PrinterSnmpOid(
                    modelo_id=first_model.id,
                    chave_metrica="name",
                    oid="1.3.6.1.2.1.1.5.0",
                    tipo_valor="string",
                    versao_snmp="2c",
                    modo_consulta="walk",
                ),
            ]
        )

        self.db.commit()

        self.assertEqual(self.db.query(PrinterSnmpOid).count(), 2)

    def test_modo_consulta_rejeita_valor_invalido(self):
        first_model = self.models[0]
        self.db.add(
            PrinterSnmpOid(
                modelo_id=first_model.id,
                chave_metrica="alert_raw",
                oid="1.3.6.1.2.1.43.18.1.1.8.1.1",
                tipo_valor="string",
                versao_snmp="2c",
                modo_consulta="bulk",
            )
        )

        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_seed_idempotente_cria_oids_iniciais(self):
        result = seed_printer_snmp_oids(self.db)

        self.assertEqual(result.created, 20)
        self.assertEqual(result.ignored, 0)
        self.assertEqual(self.db.query(PrinterSnmpOid).count(), 20)

    def test_seed_idempotente_nao_duplica_oids(self):
        seed_printer_snmp_oids(self.db)

        result = seed_printer_snmp_oids(self.db)

        self.assertEqual(result.created, 0)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.unchanged, 20)
        self.assertEqual(self.db.query(PrinterSnmpOid).count(), 20)

    def test_seed_repetido_atualiza_registros_existentes(self):
        seed_printer_snmp_oids(self.db)
        row = self.db.query(PrinterSnmpOid).filter_by(chave_metrica="alert_raw").first()
        row.oid = "1.3.6.1.2.1.999"
        row.ativo = False
        row.modo_consulta = "walk"
        self.db.commit()

        result = seed_printer_snmp_oids(self.db)

        self.assertEqual(result.updated, 1)
        self.db.refresh(row)
        self.assertEqual(row.oid, "1.3.6.1.2.1.43.18.1.1.8.1.1")
        self.assertEqual(row.modo_consulta, "get")
        self.assertTrue(row.ativo)

    def test_seed_define_modo_consulta_das_metricas_escalares_como_get(self):
        seed_printer_snmp_oids(self.db)

        for model_data in INITIAL_SNMP_OIDS:
            for metric_key in ("name", "location", "page_count_total"):
                row = self._oid_row(
                    model_data["fabricante"],
                    model_data["modelo"],
                    metric_key,
                )
                self.assertEqual(row.modo_consulta, "get")

    def test_seed_define_modo_consulta_de_alert_raw_por_modelo(self):
        seed_printer_snmp_oids(self.db)

        expected_modes = {
            ("Brother", "DCP-L1632W"): ("get", "1.3.6.1.2.1.43.18.1.1.8.1.1"),
            ("Brother", "DCP-L2540DW"): ("walk", PRT_ALERT_DESCRIPTION_BASE_OID),
            ("Canon", "IR-C3326I"): ("walk", PRT_ALERT_DESCRIPTION_BASE_OID),
            ("HP", "MFP-4303"): ("get", "1.3.6.1.2.1.25.3.5.1.1.1"),
            ("Samsung", "K-4350"): ("get", "1.3.6.1.2.1.25.3.5.1.1.1"),
        }

        for (manufacturer, model_name), (query_mode, oid) in expected_modes.items():
            row = self._oid_row(manufacturer, model_name, "alert_raw")
            self.assertEqual(row.modo_consulta, query_mode)
            self.assertEqual(row.oid, oid)

    def test_seed_ignora_modelo_inexistente_sem_quebrar(self):
        result = seed_printer_snmp_oids(
            self.db,
            entries=[
                seed_entry(
                    manufacturer="Fabricante Inexistente",
                    model_name="Modelo Inexistente",
                )
            ],
        )

        self.assertEqual(result.created, 0)
        self.assertEqual(result.ignored, 1)
        self.assertEqual(
            result.ignored_models,
            ("Fabricante Inexistente Modelo Inexistente",),
        )

    def test_seed_rejeita_modo_consulta_invalido(self):
        with self.assertRaises(ValueError):
            seed_printer_snmp_oids(
                self.db,
                entries=[seed_entry(query_mode="bulk")],
            )

    def test_oids_invalidados_de_toner_nao_entram_no_seed_ativo(self):
        entries = iter_seed_entries()

        self.assertNotIn("toner_black", {entry["chave_metrica"] for entry in entries})
        serialized = str(entries)
        for invalid in INVALIDATED_SNMP_OIDS:
            self.assertNotIn(invalid["oid"], serialized)


class PrinterSnmpOidServiceTest(TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        PrinterModel.__table__.create(engine)
        PrinterSnmpOid.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.model = PrinterModel(manufacturer="Brother", name="DCP-L1632W")
        self.db.add(self.model)
        self.db.flush()
        self.db.add_all(
            [
                PrinterSnmpOid(
                    modelo_id=self.model.id,
                    chave_metrica="alert_raw",
                    oid="1.3.6.1.2.1.43.18.1.1.8.1.1",
                    tipo_valor="string",
                    versao_snmp="2c",
                    modo_consulta="get",
                    ativo=True,
                ),
                PrinterSnmpOid(
                    modelo_id=self.model.id,
                    chave_metrica="name",
                    oid="1.3.6.1.2.1.1.5.0",
                    tipo_valor="string",
                    versao_snmp="2c",
                    modo_consulta="get",
                    ativo=True,
                ),
                PrinterSnmpOid(
                    modelo_id=self.model.id,
                    chave_metrica="location",
                    oid="1.3.6.1.2.1.1.6.0",
                    tipo_valor="string",
                    versao_snmp="2c",
                    modo_consulta="walk",
                    ativo=False,
                ),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_service_busca_oid_ativo_por_modelo_e_metrica(self):
        result = get_active_oid_for_model(
            self.db,
            model_id=self.model.id,
            metric_key="alert_raw",
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            oid_to_dict(result),
            {
                "modelo_id": self.model.id,
                "chave_metrica": "alert_raw",
                "oid": "1.3.6.1.2.1.43.18.1.1.8.1.1",
                "tipo_valor": "string",
                "versao_snmp": "2c",
                "modo_consulta": "get",
                "ativo": True,
            },
        )

    def test_service_ignora_oid_inativo(self):
        result = get_active_oid_for_model(
            self.db,
            model_id=self.model.id,
            metric_key="location",
        )

        self.assertIsNone(result)

    def test_service_retorna_none_quando_metrica_nao_existe(self):
        result = get_active_oid_for_model(
            self.db,
            model_id=self.model.id,
            metric_key="page_count_total",
        )

        self.assertIsNone(result)

    def test_service_lista_oids_ativos_de_um_modelo(self):
        result = list_active_oids_for_model(self.db, model_id=self.model.id)

        self.assertEqual(
            [row.chave_metrica for row in result],
            ["alert_raw", "name"],
        )


class PrinterSnmpOidAdminTest(TestCase):
    def test_admin_expoe_campos_filtros_e_busca(self):
        model_admin = PrinterSnmpOidAdmin(
            PrinterSnmpOidAdminModel,
            AdminSite(),
        )

        self.assertEqual(
            model_admin.list_filter,
            ("modelo", "chave_metrica", "versao_snmp", "modo_consulta", "ativo"),
        )
        self.assertIn(
            "modo_consulta",
            model_admin.list_display,
        )
        self.assertIn("modo_consulta", model_admin.list_filter)
        self.assertEqual(
            model_admin.search_fields,
            ("oid", "chave_metrica", "modelo__manufacturer", "modelo__name"),
        )
        self.assertEqual(
            set(model_admin.readonly_fields),
            {"criado_em", "atualizado_em"},
        )

    def test_admin_respeita_permissoes_basicas_do_django(self):
        model_admin = PrinterSnmpOidAdmin(
            PrinterSnmpOidAdminModel,
            AdminSite(),
        )
        technical_request = RequestStub(
            PermissionUserStub(
                {
                    "printer_machines.add_printersnmpoidadminmodel",
                    "printer_machines.change_printersnmpoidadminmodel",
                    "printer_machines.delete_printersnmpoidadminmodel",
                    "printer_machines.view_printersnmpoidadminmodel",
                }
            )
        )
        operator_request = RequestStub(PermissionUserStub())

        self.assertTrue(model_admin.has_change_permission(technical_request))
        self.assertFalse(model_admin.has_change_permission(operator_request))
        self.assertFalse(model_admin.has_add_permission(operator_request))
        self.assertFalse(model_admin.has_delete_permission(operator_request))
        self.assertEqual(
            PrinterSnmpOidAdminModel._meta.db_table,
            "oids_snmp_impressoras",
        )
        self.assertEqual(PrinterSnmpOidAdminModel._meta.app_label, "printer_machines")
        self.assertEqual(
            PrinterSnmpOidAdminModel._meta.verbose_name_plural,
            "OIDs_SNMP_IMPRESSORAS",
        )
