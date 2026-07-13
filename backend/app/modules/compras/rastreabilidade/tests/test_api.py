import datetime as dt
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.modules.audit.orm import AuditLog
from backend.app.modules.compras.rastreabilidade.models import (
    ComprasRastreabilidadeExecucao,
    ComprasRastreabilidadeItem,
)
from backend.app.modules.compras.rastreabilidade.workflow import IMPORT_LOCK_KEY
from backend.tests.auth_helpers import auth_headers


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        self.ttls[key] = ex
        return True

    def eval(self, _script, _key_count, key, token):
        if self.values.get(key) != token:
            return 0
        del self.values[key]
        self.ttls.pop(key, None)
        return 1


class ComprasRastreabilidadeApiTest(TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        AuditLog.__table__.create(engine)
        ComprasRastreabilidadeExecucao.__table__.create(engine)
        ComprasRastreabilidadeItem.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.redis = FakeRedis()

        def override_db():
            yield self.db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.headers = auth_headers(compras_rastreabilidade=True)
        self.update_headers = auth_headers(
            compras_rastreabilidade=True,
            compras_rastreabilidade_update=True,
        )

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def add_execution(self, status="concluida", origem="comando"):
        execution = ComprasRastreabilidadeExecucao(status=status, origem=origem)
        self.db.add(execution)
        self.db.commit()
        return execution

    def add_item(self, execution, **overrides):
        payload = {
            "execucao_id": execution.id,
            "filial": "01",
            "numero_sc": "SC001",
            "item_sc": "0001",
            "produto": "P001",
            "descricao_produto": "Produto seguro",
            "quantidade_sc": 10,
            "data_emissao_sc": dt.date(2026, 7, 1),
            "sc_aprovada": "Sim",
            "centro_custo": "CC-100",
            "solicitante": "Analista",
            "numero_pedido": "PC001",
            "item_pedido": "0001",
            "pedido_liberado": "Sim",
            "quantidade_recebida_almox": 10,
            "percentual_recebido": 100,
            "chegada_parcial_ou_total": "Recebido 100%",
            "nf_lancada_fiscal": "Sim",
            "virou_titulo_financeiro": "Sim",
            "status_pagamento_financeiro": "Pago",
            "local_estoque_consultado": "06",
            "status_estoque_executivo": "Entrada em consumo direto",
            "compra_efetivada": "Sim - confirmado por entrada no almoxarifado",
            "situacao_compra": "Comprado e recebido 100% no almoxarifado",
            "status_prazo_entrega": "Recebido 100% no prazo",
            "payload_completo": {"Authorization": "Bearer segredo-nao-expor"},
        }
        payload.update(overrides)
        item = ComprasRastreabilidadeItem(**payload)
        self.db.add(item)
        self.db.commit()
        return item

    def test_resumo_usa_ultima_execucao_concluida_e_ignora_parcial_e_erro(self):
        current = self.add_execution("concluida")
        self.add_item(current)
        running = self.add_execution("em_andamento", origem="manual")
        self.add_item(running, numero_sc="SC-PARCIAL", status_estoque_executivo="Sem saldo disponivel")
        failed = self.add_execution("erro", origem="agendada")
        self.add_item(failed, numero_sc="SC-ERRO")

        response = self.client.get(
            "/api/v2/compras/rastreabilidade/resumo",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["possui_dados"])
        self.assertEqual(data["execucao_id"], current.id)
        self.assertEqual(data["total_itens"], 1)
        self.assertEqual(data["com_pedido"], 1)
        self.assertEqual(data["compra_efetivada"], 1)
        self.assertEqual(data["recebido_100"], 1)
        self.assertEqual(data["consumo_direto"], 1)
        self.assertEqual(data["sem_saldo"], 0)

    def test_resumo_sem_snapshot_concluido_retorna_ausencia_segura(self):
        self.add_execution("em_andamento", origem="manual")

        response = self.client.get(
            "/api/v2/compras/rastreabilidade/resumo",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertFalse(data["possui_dados"])
        self.assertEqual(data["mensagem"], "Nenhuma importacao concluida encontrada.")

    def test_listagem_filtra_pagina_ordena_e_nao_retorna_payload_completo(self):
        execution = self.add_execution()
        self.add_item(
            execution,
            numero_sc="SC002",
            produto="P002",
            centro_custo="CC-200",
            data_emissao_sc=dt.date(2026, 7, 2),
            payload_completo={"senha": "nao-expor"},
        )
        self.add_item(
            execution,
            numero_sc="SC001",
            produto="P001",
            centro_custo="CC-100",
            data_emissao_sc=dt.date(2026, 7, 1),
        )

        response = self.client.get(
            "/api/v2/compras/rastreabilidade/itens",
            headers=self.headers,
            params={"page": 1, "page_size": 1, "centro_custo": "CC-200"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["numero_sc"], "SC002")
        self.assertNotIn("payload_completo", data["items"][0])
        self.assertNotIn("nao-expor", response.text)

    def test_detalhe_retorna_apenas_item_do_snapshot_atual(self):
        old = self.add_execution()
        old_item = self.add_item(old, numero_sc="SC-ANTIGA")
        current = self.add_execution()
        current_item = self.add_item(current, numero_sc="SC-ATUAL")

        old_response = self.client.get(
            f"/api/v2/compras/rastreabilidade/itens/{old_item.id}",
            headers=self.headers,
        )
        current_response = self.client.get(
            f"/api/v2/compras/rastreabilidade/itens/{current_item.id}",
            headers=self.headers,
        )

        self.assertEqual(old_response.status_code, 404)
        self.assertEqual(current_response.status_code, 200)
        self.assertEqual(current_response.json()["data"]["numero_sc"], "SC-ATUAL")
        self.assertNotIn("segredo-nao-expor", current_response.text)

    def test_execucoes_lista_mais_recente_primeiro_e_sanitizada(self):
        first = self.add_execution("erro", origem="agendada")
        first.mensagem_erro_sanitizada = "Falha sanitizada."
        second = self.add_execution("concluida", origem="manual")
        self.db.commit()

        response = self.client.get(
            "/api/v2/compras/rastreabilidade/execucoes",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        items = response.json()["data"]["items"]
        self.assertEqual(items[0]["id"], second.id)
        self.assertEqual(items[1]["origem"], "agendada")
        self.assertEqual(items[1]["mensagem_erro_sanitizada"], "Falha sanitizada.")
        self.assertNotIn("Traceback", response.text)
        self.assertNotIn("PWD=", response.text)

    def test_post_atualizar_retorna_202_e_enfileira_sem_executar_sincrono(self):
        calls = []

        def fake_apply_async(**kwargs):
            calls.append(kwargs)

        with patch(
            "backend.app.modules.compras.rastreabilidade.api.get_redis_client",
            return_value=self.redis,
        ), patch(
            "backend.app.modules.compras.rastreabilidade.tasks.compras_rastreabilidade_importar.apply_async",
            side_effect=fake_apply_async,
        ):
            response = self.client.post(
                "/api/v2/compras/rastreabilidade/atualizar",
                headers=self.update_headers,
            )

        self.assertEqual(response.status_code, 202)
        data = response.json()["data"]
        self.assertEqual(data["status"], "iniciada")
        self.assertEqual(self.db.query(ComprasRastreabilidadeExecucao).count(), 1)
        self.assertEqual(calls[0]["kwargs"]["origem"], "manual")
        self.assertEqual(calls[0]["kwargs"]["execucao_id"], data["execucao_id"])

    def test_post_atualizar_com_lock_ativo_retorna_em_andamento(self):
        self.redis.set(IMPORT_LOCK_KEY, "ativo")

        with patch(
            "backend.app.modules.compras.rastreabilidade.api.get_redis_client",
            return_value=self.redis,
        ):
            response = self.client.post(
                "/api/v2/compras/rastreabilidade/atualizar",
                headers=self.update_headers,
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["data"]["status"], "em_andamento")

    def test_api_exige_autenticacao_e_permissao(self):
        self.assertEqual(
            self.client.get("/api/v2/compras/rastreabilidade/resumo").status_code,
            401,
        )
        forbidden = self.client.post(
            "/api/v2/compras/rastreabilidade/atualizar",
            headers=auth_headers(compras_rastreabilidade=True, compras_rastreabilidade_update=False),
        )
        self.assertEqual(forbidden.status_code, 403)
