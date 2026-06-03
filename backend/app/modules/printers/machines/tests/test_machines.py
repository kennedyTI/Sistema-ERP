from unittest import TestCase

from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.main import app
from backend.tests.auth_helpers import auth_headers


class FakeDb:
    def add(self, _obj):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None


class PrinterMachinesApiTest(TestCase):
    def setUp(self):
        def override_db():
            yield FakeDb()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_lista_inicial_retorna_envelope_vazio(self):
        response = self.client.get(
            "/api/v2/printers/machines",
            headers=auth_headers(printers_machines=True),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])
        self.assertTrue(response.json()["success"])

    def test_lista_exige_autenticacao(self):
        response = self.client.get("/api/v2/printers/machines")

        self.assertEqual(response.status_code, 401)

    def test_lista_recusa_usuario_sem_permissao(self):
        response = self.client.get(
            "/api/v2/printers/machines",
            headers=auth_headers(portal=True, printers_machines=False),
        )

        self.assertEqual(response.status_code, 403)
