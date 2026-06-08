from unittest import TestCase

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.modules.printers.machines.models import PrinterMachine, PrinterModel
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
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        PrinterModel.__table__.create(engine)
        PrinterMachine.__table__.create(engine)
        self.session_factory = sessionmaker(bind=engine)
        self.db = self.session_factory()

        def override_db():
            yield self.db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_lista_inicial_retorna_envelope_vazio(self):
        response = self.client.get(
            "/api/v2/printers/machines",
            headers=auth_headers(printers_machines=True),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])
        self.assertTrue(response.json()["success"])

    def test_cria_lista_e_detalha_maquina(self):
        create_response = self.client.post(
            "/api/v2/printers/machines",
            headers=auth_headers(printers_machines=True),
            json={
                "name": "Impressora Expedicao",
                "ip_address": "192.168.10.25",
                "manufacturer": "HP",
                "model": "LaserJet",
                "type": "laser",
                "color_mode": "mono",
                "sector": "Expedicao",
                "cost_center": "CC-100",
                "notes": "Cadastro inicial",
            },
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()["data"]
        self.assertEqual(created["name"], "Impressora Expedicao")
        self.assertEqual(created["ip_address"], "192.168.10.25")
        self.assertIsNotNone(created["model_id"])
        self.assertEqual(created["manufacturer"], "HP")
        self.assertEqual(created["model"], "LaserJet")
        self.assertEqual(created["type"], "laser")
        self.assertEqual(created["color_mode"], "mono")
        self.assertTrue(created["is_active"])

        list_response = self.client.get(
            "/api/v2/printers/machines",
            headers=auth_headers(printers_machines=True),
        )
        self.assertEqual(len(list_response.json()["data"]), 1)

        detail_response = self.client.get(
            f"/api/v2/printers/machines/{created['id']}",
            headers=auth_headers(printers_machines=True),
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["data"]["id"], created["id"])

    def test_atualiza_maquina(self):
        create_response = self.client.post(
            "/api/v2/printers/machines",
            headers=auth_headers(printers_machines=True),
            json={"name": "Recepcao", "ip_address": "10.0.0.10"},
        )
        machine_id = create_response.json()["data"]["id"]

        response = self.client.patch(
            f"/api/v2/printers/machines/{machine_id}",
            headers=auth_headers(printers_machines=True),
            json={"name": "Recepcao Fiscal", "sector": "Fiscal"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["name"], "Recepcao Fiscal")
        self.assertEqual(response.json()["data"]["sector"], "Fiscal")

    def test_atualiza_modelo_da_maquina(self):
        create_response = self.client.post(
            "/api/v2/printers/machines",
            headers=auth_headers(printers_machines=True),
            json={"name": "Recepcao", "ip_address": "10.0.0.11"},
        )
        machine_id = create_response.json()["data"]["id"]

        response = self.client.patch(
            f"/api/v2/printers/machines/{machine_id}",
            headers=auth_headers(printers_machines=True),
            json={
                "manufacturer": "Brother",
                "model": "HL Exemplo",
                "type": "laser",
                "color_mode": "mono",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["manufacturer"], "Brother")
        self.assertEqual(data["model"], "HL Exemplo")
        self.assertEqual(data["type"], "laser")
        self.assertEqual(data["color_mode"], "mono")

    def test_recusa_ip_duplicado(self):
        headers = auth_headers(printers_machines=True)
        self.client.post(
            "/api/v2/printers/machines",
            headers=headers,
            json={"name": "A", "ip_address": "10.0.0.20"},
        )

        response = self.client.post(
            "/api/v2/printers/machines",
            headers=headers,
            json={"name": "B", "ip_address": "10.0.0.20"},
        )

        self.assertEqual(response.status_code, 409)

    def test_inativa_maquina(self):
        create_response = self.client.post(
            "/api/v2/printers/machines",
            headers=auth_headers(printers_machines=True),
            json={"name": "Producao", "ip_address": "10.0.0.30"},
        )
        machine_id = create_response.json()["data"]["id"]

        response = self.client.patch(
            f"/api/v2/printers/machines/{machine_id}/status",
            headers=auth_headers(printers_machines=True),
            json={"is_active": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["is_active"])

    def test_retorna_404_para_maquina_inexistente(self):
        response = self.client.get(
            "/api/v2/printers/machines/999",
            headers=auth_headers(printers_machines=True),
        )

        self.assertEqual(response.status_code, 404)

    def test_valida_ip_obrigatorio_e_valido(self):
        response = self.client.post(
            "/api/v2/printers/machines",
            headers=auth_headers(printers_machines=True),
            json={"name": "Sem IP", "ip_address": "ip-invalido"},
        )

        self.assertEqual(response.status_code, 422)

    def test_lista_exige_autenticacao(self):
        response = self.client.get("/api/v2/printers/machines")

        self.assertEqual(response.status_code, 401)

    def test_lista_recusa_usuario_sem_permissao(self):
        response = self.client.get(
            "/api/v2/printers/machines",
            headers=auth_headers(portal=True, printers_machines=False),
        )

        self.assertEqual(response.status_code, 403)
