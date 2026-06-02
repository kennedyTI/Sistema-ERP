from unittest import TestCase

from backend.app.modules.audit.orm import AuditLog
from backend.app.modules.audit.orm import Log
from backend.app.modules.audit import services as audit_service


class DbStub:
    def __init__(self, rows=None):
        self.rows = rows or []

    def add(self, item):
        self.rows.append(item)


class CoreModelAlignmentTest(TestCase):
    def test_logs_nao_tem_chave_de_impressora(self):
        columns = set(Log.__table__.columns.keys())

        self.assertEqual(
            columns,
            {"id", "tipo", "message", "valor_anterior", "valor_novo", "created_at"},
        )

    def test_audit_logs_mantem_estrutura_generica(self):
        columns = set(AuditLog.__table__.columns.keys())

        self.assertEqual(
            columns,
            {
                "id",
                "table_name",
                "record_id",
                "action",
                "old_data",
                "new_data",
                "changed_by",
                "source",
                "created_at",
            },
        )


class AuditLogServiceTest(TestCase):
    def test_cria_audit_log(self):
        db = DbStub()

        result = audit_service.create_audit_log(
            db=db,
            table_name="auth_events",
            record_id=None,
            action="manual_fix",
            old_data=None,
            new_data={"event": "login_success"},
            changed_by="admin",
            source="api_internal",
        )

        self.assertIs(result, db.rows[0])
        self.assertIsInstance(result, AuditLog)
        self.assertEqual(result.table_name, "auth_events")
        self.assertEqual(result.action, "manual_fix")
        self.assertEqual(result.source, "api_internal")

