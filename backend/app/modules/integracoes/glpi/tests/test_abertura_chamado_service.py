from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.modules.integracoes.glpi.config import GlpiSettings
from backend.app.modules.integracoes.glpi.exceptions import GlpiApiError
from backend.app.modules.integracoes.glpi.models.glpi_chamados import GlpiChamado
from backend.app.modules.integracoes.glpi.schemas.abertura_chamado_schema import AbrirChamadoGlpiRequest
from backend.app.modules.integracoes.glpi.services.abertura_chamado_service import abrir_chamado_glpi


class SuccessfulClient:
    def __init__(self, response=None):
        self.response = response if response is not None else {"id": 456}
        self.calls = []

    def open_ticket(self, payload):
        self.calls.append(payload)
        return self.response


class FailingClient:
    def open_ticket(self, payload):
        raise GlpiApiError("Falha controlada da API GLPI.")


class GlpiOpeningServiceTest(TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        GlpiChamado.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.settings = GlpiSettings(
            enabled=True,
            base_url="https://glpi.example.com",
            app_token="token-app-nao-persistir",
            user_token="token-user-nao-persistir",
            entity_id=1,
            printer_supply_category_id=77,
            location_cariacica_id=9,
            request_type_id=1,
        )

    def tearDown(self):
        self.db.close()

    def request(self, deduplication_hash="impressoras:maquina:1:substituir_toner:preto"):
        return AbrirChamadoGlpiRequest(
            origem_modulo="impressoras",
            origem_entidade="maquina",
            origem_entidade_id="1",
            tipo_evento="substituir_toner",
            titulo="[Impressora] Substituir toner - IMP-001 - TI",
            descricao="Descricao segura",
            hash_deduplicacao=deduplication_hash,
            metadados={"codigo_protheus": "319942"},
        )

    def test_cria_registro_salva_ticket_e_mantem_encerrado_nulo(self):
        client = SuccessfulClient()

        result = abrir_chamado_glpi(
            self.db,
            self.request(),
            settings=self.settings,
            client=client,
        )

        row = self.db.query(GlpiChamado).one()
        self.assertEqual(result.status_integracao, "aberto")
        self.assertEqual(row.glpi_ticket_id, 456)
        self.assertEqual(row.status_integracao, "aberto")
        self.assertEqual(row.tentativas, 1)
        self.assertIsNotNone(row.aberto_em)
        self.assertIsNone(row.encerrado_em)
        self.assertEqual(row.payload_enviado["input"]["itilcategories_id"], 77)
        self.assertEqual(row.payload_enviado["input"]["locations_id"], 9)

    def test_nao_abre_chamado_duplicado(self):
        client = SuccessfulClient()
        first = abrir_chamado_glpi(self.db, self.request(), settings=self.settings, client=client)
        second = abrir_chamado_glpi(self.db, self.request(), settings=self.settings, client=client)

        self.assertFalse(first.duplicado)
        self.assertTrue(second.duplicado)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(self.db.query(GlpiChamado).count(), 1)

    def test_salva_erro_e_incrementa_tentativa(self):
        result = abrir_chamado_glpi(
            self.db,
            self.request(),
            settings=self.settings,
            client=FailingClient(),
        )

        row = self.db.query(GlpiChamado).one()
        self.assertEqual(result.status_integracao, "erro")
        self.assertEqual(row.status_integracao, "erro")
        self.assertEqual(row.tentativas, 1)
        self.assertIn("Falha controlada", row.ultimo_erro)

    def test_trata_resposta_sem_ticket_id(self):
        result = abrir_chamado_glpi(
            self.db,
            self.request(),
            settings=self.settings,
            client=SuccessfulClient({"message": "sem identificador"}),
        )

        self.assertEqual(result.status_integracao, "erro")
        self.assertIn("identificador", result.erro)

    def test_bloqueia_sem_localizacao_sem_chamar_api(self):
        settings = GlpiSettings(
            enabled=True,
            base_url="https://glpi.example.com",
            app_token="placeholder",
            user_token="placeholder",
            entity_id=1,
            printer_supply_category_id=77,
            location_cariacica_id=None,
            request_type_id=1,
        )
        client = SuccessfulClient()

        result = abrir_chamado_glpi(
            self.db,
            self.request(),
            settings=settings,
            client=client,
        )

        self.assertEqual(result.status_integracao, "bloqueado_dados_incompletos")
        self.assertIn("GLPI_LOCATION_CARIACICA_ID", result.erro)
        self.assertEqual(client.calls, [])
        self.assertEqual(self.db.query(GlpiChamado).one().tentativas, 0)

    def test_nao_persiste_credenciais(self):
        abrir_chamado_glpi(
            self.db,
            self.request(),
            settings=self.settings,
            client=FailingClient(),
        )

        persisted = str(self.db.query(GlpiChamado).one().payload_enviado)
        persisted += str(self.db.query(GlpiChamado).one().ultimo_erro)
        self.assertNotIn(self.settings.app_token, persisted)
        self.assertNotIn(self.settings.user_token, persisted)
