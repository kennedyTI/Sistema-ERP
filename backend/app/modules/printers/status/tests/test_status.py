from unittest import TestCase

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.modules.audit.orm import AuditLog
from backend.app.modules.printers.machines.models import PrinterMachine, PrinterModel
from backend.app.modules.printers.status.models import LogImpressora, StatusImpressora
from backend.tests.auth_helpers import auth_headers


class PrinterStatusApiTest(TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        AuditLog.__table__.create(engine)
        PrinterModel.__table__.create(engine)
        PrinterMachine.__table__.create(engine)
        StatusImpressora.__table__.create(engine)
        LogImpressora.__table__.create(engine)
        self.session_factory = sessionmaker(bind=engine)
        self.db = self.session_factory()

        def override_db():
            yield self.db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def _create_machine(self, *, image_url=None):
        response = self.client.post(
            "/api/v2/printers/machines",
            headers=auth_headers(printers_machines=True),
            json={
                "name": "Impressora Status",
                "ip_address": "192.0.2.10",
                "manufacturer": "Fabricante Exemplo",
                "model": "Modelo Exemplo",
                "sector": "Setor Exemplo",
                "cost_center": "CC-EXEMPLO",
            },
        )
        self.assertEqual(response.status_code, 201)
        if image_url:
            model = self.db.query(PrinterModel).one()
            model.url_imagem = image_url
            self.db.commit()
        return response.json()["dados"]["maquina"]

    def test_nova_maquina_recebe_status_inicial(self):
        machine = self._create_machine(image_url="/static/imgs/printers/modelo-exemplo.png")

        response = self.client.get(
            f"/api/v2/printers/status/{machine['id']}",
            headers=auth_headers(printers_status=True),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["machine_name"], "Impressora Status")
        self.assertEqual(data["manufacturer"], "Fabricante Exemplo")
        self.assertEqual(data["model"], "Modelo Exemplo")
        self.assertEqual(data["url_imagem"], "/static/imgs/printers/modelo-exemplo.png")
        self.assertEqual(data["status_operacional"], "desconhecido")
        self.assertEqual(data["nivel_alerta"], "cinza")
        self.assertEqual(data["mensagem_operador"], "Aguardando primeira verificacao.")
        self.assertEqual(data["origem"], "sistema")

    def test_lista_status_com_envelope_padrao(self):
        self._create_machine()

        response = self.client.get(
            "/api/v2/printers/status",
            headers=auth_headers(printers_status=True),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(len(payload["data"]), 1)

    def test_lista_e_resumo_ignoram_maquinas_inativas(self):
        active_machine = self._create_machine()
        inactive_model = PrinterModel(
            manufacturer="Fabricante Inativo",
            name="Modelo Inativo",
        )
        inactive_machine = PrinterMachine(
            name="Impressora Inativa",
            ip_address="192.0.2.11",
            printer_model=inactive_model,
            is_active=False,
        )
        self.db.add(inactive_machine)
        self.db.flush()
        self.db.add(
            StatusImpressora(
                maquina_id=inactive_machine.id,
                status_operacional="offline",
                nivel_alerta="vermelho",
                mensagem_alerta="Sem comunicacao",
                mensagem_operador="Equipamento inativo",
                origem="manual",
            )
        )
        self.db.commit()
        headers = auth_headers(printers_status=True)

        list_response = self.client.get("/api/v2/printers/status", headers=headers)
        summary_response = self.client.get("/api/v2/printers/status/summary", headers=headers)

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            [status["machine_id"] for status in list_response.json()["data"]],
            [active_machine["id"]],
        )
        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.json()["data"]["total_impressoras"], 1)
        self.assertEqual(summary_response.json()["data"]["offline"], 0)
        self.assertEqual(summary_response.json()["data"]["com_alerta"], 0)

    def test_resumo_operacional_calcula_cards(self):
        machine = self._create_machine()
        status = self.db.query(StatusImpressora).filter_by(maquina_id=machine["id"]).one()
        status.status_operacional = "online"
        status.nivel_alerta = "amarelo"
        status.mensagem_alerta = "Substituir toner black"
        status.mensagem_operador = "Solicitar toner ao almoxarifado"
        self.db.commit()
        headers = auth_headers(printers_status=True)

        response = self.client.get("/api/v2/printers/status/summary", headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"],
            {
                "total_impressoras": 1,
                "online": 1,
                "offline": 0,
                "com_alerta": 1,
                "substituir_toner": 1,
            },
        )

    def test_status_operacional_nao_possui_endpoint_manual_de_edicao(self):
        machine = self._create_machine()
        headers = auth_headers(printers_status=True)

        response = self.client.patch(
            f"/api/v2/printers/status/{machine['id']}",
            headers=headers,
            json={
                "status_operacional": "online",
                "nivel_alerta": "verde",
                "mensagem_alerta": "Atualizacao manual de teste",
                "mensagem_operador": "Sem acao necessaria",
                "tempo_resposta_ms": 25,
                "origem": "manual",
                "resposta_bruta": "Resposta tecnica ficticia",
            },
        )

        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.db.query(LogImpressora).count(), 0)

    def test_operador_consulta_status_mas_nao_atualiza(self):
        machine = self._create_machine()
        operator_headers = auth_headers(printers_status=True)

        list_response = self.client.get("/api/v2/printers/status", headers=operator_headers)
        self.assertEqual(list_response.status_code, 200)

    def test_status_exige_autenticacao_e_permissao(self):
        self.assertEqual(self.client.get("/api/v2/printers/status").status_code, 401)
        response = self.client.get(
            "/api/v2/printers/status",
            headers=auth_headers(portal=True, printers_status=False),
        )
        self.assertEqual(response.status_code, 403)

    def test_status_inexistente_retorna_404(self):
        response = self.client.get(
            "/api/v2/printers/status/999",
            headers=auth_headers(printers_status=True),
        )
        self.assertEqual(response.status_code, 404)
