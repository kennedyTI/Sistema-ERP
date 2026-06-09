import os
from unittest import TestCase

import django
from django.contrib.admin.sites import AdminSite

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backoffice.settings")
django.setup()

from backend.app.modules.audit.admin import AuditLogAdmin, LogAdmin, ReadOnlyAdminMixin  # noqa: E402
from backend.app.modules.audit.models import AuditLog, Log  # noqa: E402
from backend.app.modules.backoffice.management.commands.seed_admin_groups import GROUPS, OLD_GROUP_RENAMES  # noqa: E402
from backend.app.modules.printers.status.admin import PrinterLogAdmin, PrinterStatusAdmin  # noqa: E402
from backend.app.modules.printers.status.django_models import PrinterLogAdminModel, PrinterStatusAdminModel  # noqa: E402


class StaffUserStub:
    is_active = True
    is_staff = True

    def has_perm(self, perm):
        return True


class RequestStub:
    user = StaffUserStub()
    GET = {}


class AdminPolicyTest(TestCase):
    def test_logs_e_audit_sao_somente_leitura(self):
        admin_models = (
            (LogAdmin, Log),
            (AuditLogAdmin, AuditLog),
        )
        request = RequestStub()

        for admin_class, model in admin_models:
            with self.subTest(model=model.__name__):
                admin = admin_class(model, AdminSite())

                self.assertIsInstance(admin, ReadOnlyAdminMixin)
                self.assertFalse(admin.has_add_permission(request))
                self.assertFalse(admin.has_change_permission(request))
                self.assertFalse(admin.has_delete_permission(request))
                self.assertEqual(
                    set(admin.get_readonly_fields(request)),
                    {field.name for field in model._meta.fields},
                )

    def test_log_admin_exibe_valores_para_investigacao(self):
        admin = LogAdmin(Log, AdminSite())

        self.assertIn("valor_anterior", admin.list_display)
        self.assertIn("valor_novo", admin.list_display)

    def test_status_de_impressoras_e_somente_leitura_no_admin(self):
        admin = PrinterStatusAdmin(PrinterStatusAdminModel, AdminSite())
        request = RequestStub()

        self.assertIsInstance(admin, ReadOnlyAdminMixin)
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))
        self.assertFalse(admin.has_delete_permission(request))
        self.assertEqual(
            set(admin.get_readonly_fields(request)),
            {field.name for field in PrinterStatusAdminModel._meta.fields},
        )

    def test_logs_de_impressoras_sao_somente_leitura(self):
        admin = PrinterLogAdmin(PrinterLogAdminModel, AdminSite())
        request = RequestStub()

        self.assertIsInstance(admin, ReadOnlyAdminMixin)
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))
        self.assertFalse(admin.has_delete_permission(request))


class AdminGroupsPolicyTest(TestCase):
    def test_grupos_oficiais_estao_definidos(self):
        self.assertEqual(
            set(GROUPS),
            {"Equipe T\u00e9cnica", "Gestor", "Operador", "Integra\u00e7\u00e3o Protheus"},
        )

    def test_seed_trata_grupos_legados_sem_duplicidade(self):
        self.assertEqual(
            OLD_GROUP_RENAMES,
            (
                ("Administrador", "Equipe T\u00e9cnica"),
                ("T\u00e9cnico", "Operador"),
            ),
        )

    def test_equipe_tecnica_recebe_admin_tecnico_de_impressoras(self):
        permissions = GROUPS["Equipe T\u00e9cnica"]["permissions"]

        self.assertEqual(permissions["audit"], {"view_log", "view_auditlog"})
        self.assertEqual(permissions["printer_machines"], "all")
        self.assertEqual(
            permissions["printer_status"],
            {
                "view_printerstatusadminmodel",
                "view_printerlogadminmodel",
            },
        )

    def test_demais_grupos_nao_recebem_permissoes_admin(self):
        for group_name in ("Gestor", "Operador", "Integra\u00e7\u00e3o Protheus"):
            with self.subTest(group=group_name):
                self.assertEqual(GROUPS[group_name]["permissions"], {})

