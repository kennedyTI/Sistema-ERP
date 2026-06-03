from unittest import TestCase

from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.modules.printers.paper.services import get_paper_status
from backend.tests.auth_helpers import auth_headers


class FakeDb:
    def add(self, _obj):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None


class PrinterPaperServiceTest(TestCase):
    def test_status_indica_modulo_em_desenvolvimento(self):
        status = get_paper_status()

        self.assertEqual(status.module, "printers_paper")
        self.assertEqual(status.status, "development")


class PrinterPaperApiTest(TestCase):
    def setUp(self):
        def override_db():
            yield FakeDb()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_papel_retorna_status_para_gestor(self):
        response = self.client.get(
            "/api/v2/printers/paper",
            headers=auth_headers(printers_paper=True),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "development")

    def test_papel_recusa_operador_sem_permissao(self):
        response = self.client.get(
            "/api/v2/printers/paper",
            headers=auth_headers(portal=True, printers_machines=True, printers_paper=False),
        )

        self.assertEqual(response.status_code, 403)
