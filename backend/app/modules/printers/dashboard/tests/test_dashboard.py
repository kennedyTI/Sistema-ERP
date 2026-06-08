from unittest import TestCase

from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.modules.printers.dashboard.services import get_dashboard_status
from backend.tests.auth_helpers import auth_headers


class FakeDb:
    def add(self, _obj):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None


class PrinterDashboardServiceTest(TestCase):
    def test_status_indica_modulo_em_desenvolvimento(self):
        status = get_dashboard_status()

        self.assertEqual(status.module, "printers_dashboard")
        self.assertEqual(status.status, "development")


class PrinterDashboardApiTest(TestCase):
    def setUp(self):
        def override_db():
            yield FakeDb()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_dashboard_retorna_status_para_usuario_permitido(self):
        response = self.client.get(
            "/api/v2/printers/dashboard",
            headers=auth_headers(printers_dashboard=True),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "development")
