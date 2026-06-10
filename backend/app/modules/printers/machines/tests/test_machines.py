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


class PrinterMachinesApiTest(TestCase):
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
        self.model = PrinterModel(
            manufacturer="Fabricante Exemplo",
            name="Modelo Exemplo",
            type="laser",
            color_mode="mono",
            url_imagem="/static/imgs/printers/modelo-exemplo.png",
        )
        self.db.add(self.model)
        self.db.commit()

        def override_db():
            yield self.db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.full_headers = auth_headers(
            username="tecnico",
            printers_machines=True,
        )

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def _create_machine(
        self,
        *,
        name: str = "Impressora Expedicao",
        ip_address: str = "192.168.10.25",
        active: bool = True,
        model_id: int | None = None,
    ) -> dict:
        response = self.client.post(
            "/api/v2/printers/machines",
            headers=self.full_headers,
            json={
                "nome": name,
                "endereco_ip": ip_address,
                "modelo_id": model_id or self.model.id,
                "setor": "Expedicao",
                "centro_custo": "CC-100",
                "ativo": active,
                "observacoes": "Cadastro inicial",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["dados"]["maquina"]

    def test_listagem_retorna_contrato_portugues_sem_paginacao(self):
        active = self._create_machine()
        inactive = self._create_machine(
            name="Impressora Inativa",
            ip_address="192.168.10.26",
            active=False,
        )

        response = self.client.get(
            "/api/v2/printers/machines",
            headers=self.full_headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["sucesso"])
        self.assertEqual(
            {machine["id"] for machine in payload["dados"]},
            {active["id"], inactive["id"]},
        )
        self.assertIn("nome", payload["dados"][0])
        self.assertIn("endereco_ip", payload["dados"][0])
        self.assertNotIn("name", payload["dados"][0])

    def test_summary_conta_total_ativos_inativos_fabricantes_e_modelos(self):
        self._create_machine()
        self._create_machine(
            name="Impressora Inativa",
            ip_address="192.168.10.26",
            active=False,
        )
        self.db.add(
            PrinterModel(
                manufacturer="Outro Fabricante",
                name="Modelo sem maquina",
            )
        )
        self.db.commit()

        response = self.client.get(
            "/api/v2/printers/machines/summary",
            headers=self.full_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["dados"],
            {
                "total_maquinas": 2,
                "ativas": 1,
                "inativas": 1,
                "fabricantes": 1,
                "modelos_cadastrados": 2,
            },
        )

    def test_details_retorna_modelo_status_logs_acoes_e_url_imagem(self):
        machine = self._create_machine()
        self.db.add(
            LogImpressora(
                maquina_id=machine["id"],
                tipo_evento="erro_sistema",
                mensagem="Evento ficticio",
                origem="sistema",
            )
        )
        self.db.commit()

        response = self.client.get(
            f"/api/v2/printers/machines/{machine['id']}/details",
            headers=self.full_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["dados"]
        self.assertEqual(data["maquina"]["url_imagem"], self.model.url_imagem)
        self.assertEqual(data["modelo_dados"]["modelo"], self.model.name)
        self.assertEqual(data["status_operacional"]["status"], "desconhecido")
        self.assertEqual(data["logs_recentes"][0]["mensagem"], "Evento ficticio")
        self.assertEqual(
            data["acoes"],
            {"pode_editar": True, "pode_alternar_status": True},
        )

    def test_edicao_transacional_salva_e_registra_auditoria(self):
        machine = self._create_machine()

        response = self.client.patch(
            f"/api/v2/printers/machines/{machine['id']}",
            headers=self.full_headers,
            json={
                "nome": "Impressora Fiscal",
                "endereco_ip": "192.168.10.30",
                "modelo_id": self.model.id,
                "setor": "Fiscal",
                "centro_custo": "CC-200",
                "observacoes": "Atualizada",
                "atualizado_em": machine["atualizado_em"],
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        updated = response.json()["dados"]["maquina"]
        self.assertEqual(updated["nome"], "Impressora Fiscal")
        self.assertEqual(updated["setor"], "Fiscal")
        audit = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.record_id == machine["id"],
                AuditLog.action == "update",
            )
            .one()
        )
        self.assertEqual(audit.changed_by, "tecnico")
        self.assertIn("nome", audit.new_data["alteracoes"])

    def test_edicao_retorna_erros_por_campo_e_nao_salva_parcialmente(self):
        first = self._create_machine()
        second = self._create_machine(
            name="Segunda Impressora",
            ip_address="192.168.10.26",
        )

        response = self.client.patch(
            f"/api/v2/printers/machines/{first['id']}",
            headers=self.full_headers,
            json={
                "nome": "Nome que nao deve persistir",
                "endereco_ip": second["endereco_ip"],
                "modelo_id": self.model.id,
                "atualizado_em": first["atualizado_em"],
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("endereco_ip", response.json()["erros"])
        self.db.expire_all()
        unchanged = self.db.get(PrinterMachine, first["id"])
        self.assertEqual(unchanged.name, first["nome"])
        self.assertEqual(unchanged.ip_address, first["endereco_ip"])

    def test_edicao_detecta_conflito_por_atualizado_em(self):
        machine = self._create_machine()
        first_response = self.client.patch(
            f"/api/v2/printers/machines/{machine['id']}",
            headers=self.full_headers,
            json={
                "nome": "Primeira alteracao",
                "modelo_id": self.model.id,
                "atualizado_em": machine["atualizado_em"],
            },
        )
        self.assertEqual(first_response.status_code, 200)

        conflict = self.client.patch(
            f"/api/v2/printers/machines/{machine['id']}",
            headers=self.full_headers,
            json={
                "nome": "Alteracao concorrente",
                "modelo_id": self.model.id,
                "atualizado_em": machine["atualizado_em"],
            },
        )

        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(
            conflict.json()["erros"]["atualizado_em"],
            ["Registro desatualizado."],
        )

    def test_edicao_recusa_modelo_inexistente(self):
        machine = self._create_machine()

        response = self.client.patch(
            f"/api/v2/printers/machines/{machine['id']}",
            headers=self.full_headers,
            json={
                "modelo_id": 999,
                "atualizado_em": machine["atualizado_em"],
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("modelo_id", response.json()["erros"])

    def test_toggle_altera_apenas_status_cadastral_e_retorna_summary(self):
        machine = self._create_machine()
        status_before = self.db.query(StatusImpressora).filter_by(maquina_id=machine["id"]).one()
        operational_before = status_before.status_operacional

        response = self.client.patch(
            f"/api/v2/printers/machines/{machine['id']}/status",
            headers=self.full_headers,
            json={"ativo": False},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["dados"]
        self.assertFalse(data["maquina"]["ativo"])
        self.assertEqual(data["resumo"]["inativas"], 1)
        self.db.expire_all()
        status_after = self.db.query(StatusImpressora).filter_by(maquina_id=machine["id"]).one()
        self.assertEqual(status_after.status_operacional, operational_before)
        audit = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.record_id == machine["id"],
                AuditLog.action == "update",
            )
            .one()
        )
        self.assertEqual(audit.new_data["ativo"], False)

    def test_toggle_sem_permissao_retorna_403(self):
        machine = self._create_machine()
        headers = auth_headers(
            printers_machines=True,
            printers_machines_toggle=False,
        )

        response = self.client.patch(
            f"/api/v2/printers/machines/{machine['id']}/status",
            headers=headers,
            json={"ativo": False},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["sucesso"])

    def test_operador_nao_acessa_maquinas(self):
        response = self.client.get(
            "/api/v2/printers/machines",
            headers=auth_headers(
                groups=["Operador"],
                printers_dashboard=True,
                printers_status=True,
                printers_machines=False,
            ),
        )

        self.assertEqual(response.status_code, 403)

    def test_listagem_exige_autenticacao(self):
        response = self.client.get("/api/v2/printers/machines")

        self.assertEqual(response.status_code, 401)
