from unittest import TestCase

from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.main import app


class DbStub:
    pass


class ApiContractsTest(TestCase):
    def setUp(self):
        def override_db():
            yield DbStub()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def assert_success_envelope(self, response):
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertIsNone(payload["errors"])
        self.assertIsInstance(payload["message"], str)
        return payload["data"]

    def test_health_check_usa_envelope_padrao(self):
        response = self.client.get("/")

        data = self.assert_success_envelope(response)
        self.assertEqual(data, {"status": "ok"})

    def test_superficie_publica_nao_expoe_rotas_operacionais_de_impressoras(self):
        forbidden = (
            "/api/v1/dashboard/summary",
            "/api/v1/dashboard/printers",
            "/api/v1/printers",
            "/api/v1/paper/summary",
            "/api/v1/protheus/supplies",
            "/api/v1/alerts/",
            "/api/v1/toner-status/",
            "/api/v1/printer-status/",
        )

        for endpoint in forbidden:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 404)

    def test_rotas_auth_v2_estao_disponiveis(self):
        paths = {route.path for route in app.routes}

        self.assertIn("/api/v2/auth/login", paths)
        self.assertIn("/api/v2/auth/me", paths)
        self.assertIn("/api/v2/auth/logout", paths)

    def test_rotas_iniciais_de_impressoras_estao_disponiveis_apenas_na_v2(self):
        paths = {route.path for route in app.routes}

        self.assertIn("/api/v2/printers/dashboard", paths)
        self.assertIn("/api/v2/printers/machines", paths)
        self.assertIn("/api/v2/printers/machines/{machine_id}", paths)
        self.assertIn("/api/v2/printers/machines/{machine_id}/status", paths)
        self.assertIn("/api/v2/printers/paper", paths)
        self.assertNotIn("/api/v1/printers/machines", paths)

