import os
from unittest import TestCase

import django
from django.contrib.admin.sites import AdminSite
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backoffice.settings")
django.setup()

from backend.app.modules.printers.monitoring.state.admin import (  # noqa: E402
    PrinterAlertRuleAdmin,
)
from backend.app.modules.printers.monitoring.state.django_models import (  # noqa: E402
    PrinterAlertRuleAdminModel,
)
from backend.app.modules.printers.monitoring.state.models import (  # noqa: E402
    PrinterAlertRule,
)
from backend.app.modules.printers.monitoring.state.rules import (  # noqa: E402
    classify_alert,
    match_rule,
    normalize_text,
)
from backend.app.modules.printers.monitoring.state.seed import (  # noqa: E402
    INITIAL_ALERT_RULES,
    seed_alert_rules,
)


def make_rule(
    codigo: str,
    padrao: str,
    *,
    prioridade: int = 50,
    severidade: str = "medium",
    tipo_regra: str = "contains",
    ativo: bool = True,
    descricao: str | None = None,
) -> PrinterAlertRule:
    return PrinterAlertRule(
        codigo=codigo,
        descricao=descricao or codigo,
        severidade=severidade,
        tipo_regra=tipo_regra,
        padrao=padrao,
        prioridade=prioridade,
        ativo=ativo,
    )


class PermissionUserStub:
    is_active = True
    is_staff = True
    is_authenticated = True

    def __init__(self, permissions=()):
        self.permissions = set(permissions)

    def has_perm(self, permission):
        return permission in self.permissions

    def get_username(self):
        return "usuario_teste"


class RequestStub:
    GET = {}

    def __init__(self, user):
        self.user = user


class AlertRuleSeedTest(TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        PrinterAlertRule.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_seed_idempotente_cria_regras_iniciais(self):
        result = seed_alert_rules(self.db)

        self.assertEqual(result.created, len(INITIAL_ALERT_RULES))
        self.assertEqual(
            self.db.query(PrinterAlertRule).count(),
            len(INITIAL_ALERT_RULES),
        )
        self.assertEqual(
            {rule["codigo"] for rule in INITIAL_ALERT_RULES},
            {
                "error",
                "offline",
                "sem_servico",
                "replace_toner",
                "replace_drum",
                "paper_jam",
                "paper_jam_inside",
                "cover_open",
                "no_paper",
                "no_paper_tray_b1",
                "maintenance",
                "memory_full",
                "paper_low",
                "drum_low",
                "toner_low",
                "idle",
                "sleep",
                "ok",
                "unknown",
                "sem_retorno_alerta",
                "falha_coleta_alertas",
            },
        )

    def test_seed_idempotente_nao_duplica_e_atualiza_campos_controlados(self):
        seed_alert_rules(self.db)
        rule = self.db.query(PrinterAlertRule).filter_by(codigo="idle").one()
        rule.descricao = "Valor local desatualizado"
        self.db.commit()

        result = seed_alert_rules(self.db)

        self.assertEqual(result.created, 0)
        self.assertEqual(result.updated, len(INITIAL_ALERT_RULES))
        self.assertEqual(
            self.db.query(PrinterAlertRule).count(),
            len(INITIAL_ALERT_RULES),
        )
        self.assertEqual(
            self.db.query(PrinterAlertRule)
            .filter_by(codigo="idle")
            .one()
            .descricao,
            "Estado normal / em espera",
        )


class AlertRulesEngineTest(TestCase):
    def test_conjunto_inicial_respeita_prioridade_entre_regras(self):
        rules = [make_rule(**item) for item in INITIAL_ALERT_RULES]

        self.assertEqual(
            classify_alert("Erro: substituir toner", rules)["codigo"],
            "error",
        )
        self.assertEqual(
            classify_alert("Substituir toner", rules)["codigo"],
            "replace_toner",
        )
        self.assertEqual(
            classify_alert("Toner baixo", rules)["codigo"],
            "toner_low",
        )
        self.assertEqual(
            classify_alert("paper is out (a4).", rules)["codigo"],
            "no_paper",
        )

    def test_regra_contains_reconhece_alerta(self):
        result = classify_alert(
            "O equipamento esta com toner baixo",
            [make_rule("toner_low", "toner baixo")],
        )

        self.assertEqual(result["codigo"], "toner_low")
        self.assertTrue(result["reconhecido"])

    def test_regra_equals_reconhece_alerta(self):
        result = classify_alert(
            "PRONTA",
            [make_rule("ok", "pronta", tipo_regra="equals", severidade="green")],
        )

        self.assertEqual(result["codigo"], "ok")

    def test_regra_regex_reconhece_alerta(self):
        self.assertTrue(
            match_rule(
                "regex",
                r"replace\\s+toner|substituir\\s+toner",
                normalize_text("Substituir toner"),
            )
        )

    def test_normalizacao_ignora_caixa_alta_e_baixa(self):
        self.assertEqual(normalize_text("ToNeR BaIxO"), "toner baixo")

    def test_normalizacao_trata_acentos(self):
        result = classify_alert(
            "Impressora em MANUTENCAO",
            [make_rule("maintenance", "manutencao")],
        )

        self.assertEqual(normalize_text("Manutenção"), "manutencao")
        self.assertEqual(result["codigo"], "maintenance")

    def test_regras_inativas_sao_ignoradas(self):
        result = classify_alert(
            "toner vazio",
            [
                make_rule("replace_toner", "toner vazio", ativo=False),
                make_rule(
                    "unknown",
                    "",
                    prioridade=999,
                    descricao="Alerta nao reconhecido",
                ),
            ],
        )

        self.assertEqual(result["codigo"], "unknown")
        self.assertFalse(result["reconhecido"])

    def test_prioridade_menor_vence(self):
        result = classify_alert(
            "paper jam detected",
            [
                make_rule("generic", "paper", prioridade=50),
                make_rule("paper_jam", "paper jam", prioridade=10, severidade="high"),
            ],
        )

        self.assertEqual(result["codigo"], "paper_jam")

    def test_empate_de_prioridade_desempata_por_codigo(self):
        result = classify_alert(
            "toner needs attention",
            [
                make_rule("z_alert", "toner", prioridade=10, severidade="high"),
                make_rule("a_alert", "toner", prioridade=10),
            ],
        )

        self.assertEqual(result["codigo"], "a_alert")

    def test_idle_em_espera_retorna_green(self):
        rule = next(item for item in INITIAL_ALERT_RULES if item["codigo"] == "idle")
        result = classify_alert("Em espera", [make_rule(**rule)])

        self.assertEqual(result["codigo"], "idle")
        self.assertEqual(result["severidade"], "green")
        self.assertEqual(result["prioridade"], 100)

    def test_sleep_dormindo_retorna_green(self):
        rule = next(item for item in INITIAL_ALERT_RULES if item["codigo"] == "sleep")
        result = classify_alert("Dormindo", [make_rule(**rule)])

        self.assertEqual(result["codigo"], "sleep")
        self.assertEqual(result["severidade"], "green")

    def test_estado_normal_retorna_green(self):
        rule = next(item for item in INITIAL_ALERT_RULES if item["codigo"] == "ok")
        result = classify_alert("Estado normal", [make_rule(**rule)])

        self.assertEqual(result["codigo"], "ok")
        self.assertEqual(result["severidade"], "green")

    def test_alertas_abreviados_de_papel_retornam_medium(self):
        cases = {
            "Atol. dentro": "paper_jam_inside",
            "S/ Papel B1": "no_paper_tray_b1",
        }
        rules = [
            make_rule(**item)
            for item in INITIAL_ALERT_RULES
            if item["codigo"] in set(cases.values())
        ]

        for message, expected_code in cases.items():
            with self.subTest(message=message):
                result = classify_alert(message, rules)
                self.assertEqual(result["codigo"], expected_code)
                self.assertEqual(result["severidade"], "medium")

    def test_imprimindo_retorna_green(self):
        rule = next(item for item in INITIAL_ALERT_RULES if item["codigo"] == "ok")
        result = classify_alert("Imprimindo", [make_rule(**rule)])

        self.assertEqual(result["codigo"], "ok")
        self.assertEqual(result["severidade"], "green")

    def test_ok_reconhece_aliases_de_impressao(self):
        rule = next(item for item in INITIAL_ALERT_RULES if item["codigo"] == "ok")

        for message in ("Printing", "A imprimir", "Em impressao", "Em impressão", "Aquecendo"):
            with self.subTest(message=message):
                result = classify_alert(message, [make_rule(**rule)])

                self.assertEqual(result["codigo"], "ok")
                self.assertEqual(result["severidade"], "green")

    def test_toner_low_retorna_medium(self):
        rule = next(
            item for item in INITIAL_ALERT_RULES if item["codigo"] == "toner_low"
        )
        for message in ("Toner is low (black)", "Ha pouco toner"):
            with self.subTest(message=message):
                result = classify_alert(message, [make_rule(**rule)])

                self.assertEqual(result["codigo"], "toner_low")
                self.assertEqual(result["severidade"], "medium")

    def test_replace_toner_retorna_high(self):
        rule = next(
            item
            for item in INITIAL_ALERT_RULES
            if item["codigo"] == "replace_toner"
        )
        result = classify_alert("Substituir toner", [make_rule(**rule)])

        self.assertEqual(result["codigo"], "replace_toner")
        self.assertEqual(result["severidade"], "high")

    def test_replace_toner_reconhece_abreviacao_com_artigo(self):
        rule = next(
            item
            for item in INITIAL_ALERT_RULES
            if item["codigo"] == "replace_toner"
        )
        result = classify_alert("Subs. o toner", [make_rule(**rule)])

        self.assertEqual(result["codigo"], "replace_toner")
        self.assertEqual(result["severidade"], "high")

    def test_replace_toner_reconhece_aliases_criticos(self):
        rule = next(
            item
            for item in INITIAL_ALERT_RULES
            if item["codigo"] == "replace_toner"
        )

        for message in (
            "Subst. toner",
            "subst toner",
            "subs. toner",
            "subs. o toner",
            "toner replace",
            "sem toner",
        ):
            with self.subTest(message=message):
                result = classify_alert(message, [make_rule(**rule)])

                self.assertEqual(result["codigo"], "replace_toner")
                self.assertEqual(result["severidade"], "high")

    def test_replace_drum_reconhece_abreviacao(self):
        rule = next(
            item
            for item in INITIAL_ALERT_RULES
            if item["codigo"] == "replace_drum"
        )
        result = classify_alert("Subst. cilindro", [make_rule(**rule)])

        self.assertEqual(result["codigo"], "replace_drum")
        self.assertEqual(result["severidade"], "high")

    def test_replace_drum_reconhece_aliases_criticos(self):
        rule = next(
            item
            for item in INITIAL_ALERT_RULES
            if item["codigo"] == "replace_drum"
        )

        for message in (
            "subst cilindro",
            "subs. cilindro",
            "subst. o cilindro",
            "substitua cilindro",
            "troque cilindro",
        ):
            with self.subTest(message=message):
                result = classify_alert(message, [make_rule(**rule)])

                self.assertEqual(result["codigo"], "replace_drum")
                self.assertEqual(result["severidade"], "high")

    def test_sem_servico_retorna_high(self):
        rule = next(
            item
            for item in INITIAL_ALERT_RULES
            if item["codigo"] == "sem_servico"
        )
        result = classify_alert("Sem serviço", [make_rule(**rule)])

        self.assertEqual(result["codigo"], "sem_servico")
        self.assertEqual(result["severidade"], "high")

    def test_paper_jam_retorna_high(self):
        rule = next(
            item for item in INITIAL_ALERT_RULES if item["codigo"] == "paper_jam"
        )
        result = classify_alert("Atolamento de papel", [make_rule(**rule)])

        self.assertEqual(result["codigo"], "paper_jam")
        self.assertEqual(result["severidade"], "high")

    def test_mensagem_desconhecida_retorna_unknown(self):
        unknown = next(
            item for item in INITIAL_ALERT_RULES if item["codigo"] == "unknown"
        )
        result = classify_alert(
            "Mensagem estranha nao mapeada",
            [make_rule(**unknown)],
        )

        self.assertEqual(result["codigo"], "unknown")
        self.assertEqual(result["severidade"], "unknown")
        self.assertFalse(result["reconhecido"])

    def test_mensagem_original_e_preservada(self):
        original = "  Mensagem Estranha com Acento: não mapeada  "
        result = classify_alert(original, [])

        self.assertEqual(result["mensagem_original"], original)


class AlertRulesAdminTest(TestCase):
    def test_admin_expoe_campos_filtros_e_busca(self):
        model_admin = PrinterAlertRuleAdmin(
            PrinterAlertRuleAdminModel,
            AdminSite(),
        )

        self.assertEqual(
            model_admin.list_filter,
            ("severidade", "tipo_regra", "ativo"),
        )
        self.assertEqual(
            model_admin.search_fields,
            ("codigo", "descricao", "padrao"),
        )
        self.assertEqual(
            set(model_admin.readonly_fields),
            {"criado_em", "atualizado_em"},
        )

    def test_admin_respeita_permissoes_basicas_do_django(self):
        model_admin = PrinterAlertRuleAdmin(
            PrinterAlertRuleAdminModel,
            AdminSite(),
        )
        technical_request = RequestStub(
            PermissionUserStub(
                {
                    "printer_alert_rules.add_printeralertruleadminmodel",
                    "printer_alert_rules.change_printeralertruleadminmodel",
                    "printer_alert_rules.delete_printeralertruleadminmodel",
                    "printer_alert_rules.view_printeralertruleadminmodel",
                }
            )
        )
        operator_request = RequestStub(PermissionUserStub())

        self.assertTrue(model_admin.has_change_permission(technical_request))
        self.assertFalse(model_admin.has_change_permission(operator_request))
        self.assertFalse(model_admin.has_add_permission(operator_request))
        self.assertFalse(model_admin.has_delete_permission(operator_request))
        self.assertEqual(
            PrinterAlertRuleAdminModel._meta.db_table,
            "regras_alertas_impressoras",
        )
