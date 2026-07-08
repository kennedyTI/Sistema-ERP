from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.timezone import now_sao_paulo
from backend.app.modules.integracoes.glpi.config import GlpiSettings
from backend.app.modules.integracoes.glpi.schemas.abertura_chamado_schema import ResultadoAberturaGlpi
from backend.app.modules.printers.integrations.glpi_service import process_confirmed_printer_supply_alerts
from backend.app.modules.printers.machines.models import PrinterMachine, PrinterModel
from backend.app.modules.printers.monitoring.alerts.models import AlertaImpressora
from backend.app.modules.printers.monitoring.state.models import PrinterAlertRule
from backend.app.modules.printers.status.models import (  # noqa: F401
    HistoricoStatusImpressora,
    LogImpressora,
    StatusImpressora,
)
from backend.app.modules.printers.supplies.models import PrinterSupply
from backend.app.modules.printers.supplies.seed import seed_printer_supplies
from backend.app.modules.printers.supplies.services import (
    get_cylinder_supply,
    get_toner_supplies,
    resolve_toner_supply,
)


class PrinterSuppliesTest(TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        PrinterModel.__table__.create(engine)
        PrinterMachine.__table__.create(engine)
        PrinterAlertRule.__table__.create(engine)
        AlertaImpressora.__table__.create(engine)
        PrinterSupply.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.models = {}
        for manufacturer, name in (
            ("Brother", "DCP-L1632W"),
            ("Brother", "DCP-L2540DW"),
            ("Canon", "IR-C3326I"),
            ("HP", "MFP-4303"),
            ("Samsung", "K-4350"),
        ):
            model = PrinterModel(manufacturer=manufacturer, name=name)
            self.db.add(model)
            self.db.flush()
            self.models[(manufacturer.upper(), name.upper())] = model
        self.db.commit()
        seed_printer_supplies(self.db)

    def tearDown(self):
        self.db.close()

    def test_busca_toner_preto_em_modelo_monocromatico(self):
        model = self.models[("BROTHER", "DCP-L1632W")]
        toner = resolve_toner_supply(self.db, model_id=model.id, message="Subs. toner")

        self.assertEqual(toner.cor, "PRETO")
        self.assertEqual(toner.codigo_protheus, "319942")

    def test_busca_multiplos_toners_em_modelo_colorido(self):
        model = self.models[("CANON", "IR-C3326I")]
        toners = get_toner_supplies(self.db, model.id)

        self.assertEqual({toner.cor for toner in toners}, {"PRETO", "CIANO", "MAGENTA", "AMARELO"})
        magenta = resolve_toner_supply(
            self.db,
            model_id=model.id,
            message="Replace toner (magenta)",
        )
        self.assertEqual(magenta.codigo_protheus, "319900")

    def test_busca_cilindro(self):
        model = self.models[("CANON", "IR-C3326I")]
        cylinder = get_cylinder_supply(self.db, model.id)

        self.assertIsNotNone(cylinder)
        self.assertEqual(cylinder.codigo_protheus, "320015")

    def test_seed_e_idempotente_e_preserva_codigo_ausente(self):
        before = self.db.query(PrinterSupply).count()
        result = seed_printer_supplies(self.db)
        after = self.db.query(PrinterSupply).count()
        samsung = self.models[("SAMSUNG", "K-4350")]
        samsung_toner = get_toner_supplies(self.db, samsung.id)[0]

        self.assertEqual(before, after)
        self.assertGreater(result.updated, 0)
        self.assertIsNone(samsung_toner.codigo_protheus)

    def _create_alert(self, *, manufacturer, model_name, code, message):
        model = self.models[(manufacturer.upper(), model_name.upper())]
        machine = PrinterMachine(
            name=f"IMP-{model.id}",
            ip_address=f"192.0.2.{model.id}",
            model_id=model.id,
            sector="Tecnologia",
            cost_center="CC-100",
            is_active=True,
        )
        rule = PrinterAlertRule(
            codigo=code,
            descricao=code,
            severidade="high",
            tipo_regra="contains",
            padrao=code,
            prioridade=1,
            ativo=True,
        )
        self.db.add_all([machine, rule])
        self.db.flush()
        alert = AlertaImpressora(
            maquina_id=machine.id,
            regra_alerta_id=rule.id,
            mensagem_original=message,
            mensagem_original_normalizada=message.casefold(),
            origem_coleta="snmp",
            metodo_confirmacao="snmp_walk",
            metodo_coleta="walk",
            chave_alerta=f"snmp:walk:{code}",
            verificado_em=now_sao_paulo(),
        )
        self.db.add(alert)
        self.db.commit()
        return machine

    @staticmethod
    def _settings():
        return GlpiSettings(
            enabled=True,
            base_url="https://glpi.example.com",
            app_token="placeholder",
            user_token="placeholder",
            printer_supply_category_id=77,
            location_cariacica_id=9,
        )

    def test_monta_chamado_de_toner_com_codigo_e_hash_exato(self):
        machine = self._create_alert(
            manufacturer="Brother",
            model_name="DCP-L1632W",
            code="replace_toner",
            message="Substituir toner",
        )
        captured = []

        def opener(db, request, settings):
            captured.append(request)
            return ResultadoAberturaGlpi(
                registro_id=1,
                status_integracao="aberto",
                glpi_ticket_id=100,
            )

        results = process_confirmed_printer_supply_alerts(
            self.db,
            machine_id=machine.id,
            settings=self._settings(),
            opener=opener,
        )

        self.assertEqual(results[0].status_integracao, "aberto")
        self.assertEqual(
            captured[0].hash_deduplicacao,
            f"impressoras:maquina:{machine.id}:substituir_toner:preto",
        )
        self.assertIn("Codigo Protheus: 319942", captured[0].descricao)
        self.assertIn("Ramal: 1010", captured[0].descricao)

    def test_bloqueia_toner_sem_codigo_protheus(self):
        machine = self._create_alert(
            manufacturer="Samsung",
            model_name="K-4350",
            code="replace_toner",
            message="Substituir toner preto",
        )
        blocked = []

        def blocker(db, request, erro, settings):
            blocked.append(erro)
            return ResultadoAberturaGlpi(
                registro_id=1,
                status_integracao="bloqueado_dados_incompletos",
                erro=erro,
            )

        process_confirmed_printer_supply_alerts(
            self.db,
            machine_id=machine.id,
            settings=self._settings(),
            blocker=blocker,
        )

        self.assertEqual(len(blocked), 1)
        self.assertIn("Codigo Protheus nao cadastrado", blocked[0])
        self.assertIn("SAMSUNG K-4350", blocked[0].upper())

    def test_bloqueia_cor_nao_identificada_em_impressora_colorida(self):
        machine = self._create_alert(
            manufacturer="Canon",
            model_name="IR-C3326I",
            code="replace_toner",
            message="Substituir toner",
        )
        opened = []
        blocked = []

        def opener(db, request, settings):
            opened.append(request)

        def blocker(db, request, erro, settings):
            blocked.append(erro)
            return ResultadoAberturaGlpi(
                registro_id=1,
                status_integracao="bloqueado_dados_incompletos",
                erro=erro,
            )

        process_confirmed_printer_supply_alerts(
            self.db,
            machine_id=machine.id,
            settings=self._settings(),
            opener=opener,
            blocker=blocker,
        )

        self.assertEqual(opened, [])
        self.assertIn("Cor do toner nao identificada", blocked[0])

    def test_monta_chamado_de_cilindro(self):
        machine = self._create_alert(
            manufacturer="Brother",
            model_name="DCP-L2540DW",
            code="replace_drum",
            message="Substituir cilindro",
        )
        captured = []

        def opener(db, request, settings):
            captured.append(request)
            return ResultadoAberturaGlpi(registro_id=1, status_integracao="aberto")

        process_confirmed_printer_supply_alerts(
            self.db,
            machine_id=machine.id,
            settings=self._settings(),
            opener=opener,
        )

        self.assertEqual(
            captured[0].hash_deduplicacao,
            f"impressoras:maquina:{machine.id}:substituir_cilindro",
        )
        self.assertIn("Codigo Protheus: 320516", captured[0].descricao)

    def test_nao_abre_chamado_para_toner_baixo(self):
        machine = self._create_alert(
            manufacturer="Brother",
            model_name="DCP-L1632W",
            code="toner_low",
            message="Toner baixo",
        )
        opened = []

        def opener(db, request, settings):
            opened.append(request)

        results = process_confirmed_printer_supply_alerts(
            self.db,
            machine_id=machine.id,
            settings=self._settings(),
            opener=opener,
        )

        self.assertEqual(results, [])
        self.assertEqual(opened, [])
