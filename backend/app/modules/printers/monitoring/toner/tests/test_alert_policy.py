from types import SimpleNamespace
from unittest import TestCase

from backend.app.modules.printers.monitoring.toner.alert_policy import (
    DEFAULT_CRITICAL_TONER_THRESHOLD,
    DEFAULT_LOW_TONER_THRESHOLD,
    TonerThresholds,
    reconcile_toner_alerts,
    resolve_toner_thresholds,
    toner_percentage_alerts,
)


def toner(percentual, *, cor="black"):
    return SimpleNamespace(percentual=percentual, cor=cor)


def textual_alert(code="replace_toner", message="Subs. toner", severity="high"):
    return {
        "codigo": code,
        "mensagem": message,
        "nivel_alerta": "vermelho" if severity == "high" else "amarelo",
        "severidade": severity,
        "prioridade": 8,
    }


class TonerAlertPolicyTest(TestCase):
    def test_threshold_padrao_e_critico_dez_e_baixo_vinte(self):
        thresholds = resolve_toner_thresholds(None)

        self.assertEqual(thresholds.critical, DEFAULT_CRITICAL_TONER_THRESHOLD)
        self.assertEqual(thresholds.low, DEFAULT_LOW_TONER_THRESHOLD)
        self.assertEqual((thresholds.critical, thresholds.low), (10, 20))

    def test_percentual_dez_gera_high(self):
        alerts = toner_percentage_alerts([toner(10)], thresholds=TonerThresholds())

        self.assertEqual(alerts[0]["codigo"], "toner_percentual_critico")
        self.assertEqual(alerts[0]["severidade"], "high")

    def test_percentual_onze_gera_medium(self):
        alerts = toner_percentage_alerts([toner(11)], thresholds=TonerThresholds())

        self.assertEqual(alerts[0]["codigo"], "toner_percentual_baixo")
        self.assertEqual(alerts[0]["severidade"], "medium")

    def test_percentual_vinte_gera_medium(self):
        alerts = toner_percentage_alerts([toner(20)], thresholds=TonerThresholds())

        self.assertEqual(alerts[0]["severidade"], "medium")

    def test_percentual_vinte_e_um_nao_gera_alerta(self):
        self.assertEqual(
            toner_percentage_alerts([toner(21)], thresholds=TonerThresholds()),
            [],
        )

    def test_percentual_acima_de_vinte_e_um_nao_gera_alerta(self):
        self.assertEqual(
            toner_percentage_alerts([toner(35)], thresholds=TonerThresholds()),
            [],
        )

    def test_percentual_nulo_nao_gera_alerta_calculado(self):
        self.assertEqual(
            toner_percentage_alerts([toner(None)], thresholds=TonerThresholds()),
            [],
        )

    def test_percentual_nulo_preserva_fallback_textual(self):
        current = textual_alert()

        alerts = reconcile_toner_alerts([current], [toner(None)], printer_model=None)

        self.assertEqual(alerts, [current])

    def test_substituir_toner_com_dezoito_vira_baixo_medium(self):
        alerts = reconcile_toner_alerts(
            [textual_alert()],
            [toner(18)],
            printer_model=None,
        )

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["mensagem"], "Toner Preto baixo: 18%")
        self.assertEqual(alerts[0]["severidade"], "medium")

    def test_substituir_toner_com_oito_vira_critico_high(self):
        alerts = reconcile_toner_alerts(
            [textual_alert()],
            [toner(8)],
            printer_model=None,
        )

        self.assertEqual(alerts[0]["mensagem"], "Toner Preto crítico: 8%")
        self.assertEqual(alerts[0]["severidade"], "high")

    def test_substituir_toner_com_vinte_e_um_e_removido(self):
        alerts = reconcile_toner_alerts(
            [textual_alert()],
            [toner(21)],
            printer_model=None,
        )

        self.assertEqual(alerts, [])

    def test_pouco_toner_com_trinta_e_cinco_e_removido(self):
        alerts = reconcile_toner_alerts(
            [textual_alert("toner_low", "Há pouco toner", "medium")],
            [toner(35)],
            printer_model=None,
        )

        self.assertEqual(alerts, [])

    def test_alerta_de_cilindro_nao_e_sobrescrito(self):
        cylinder = textual_alert("replace_drum", "Trocar cilindro", "high")

        alerts = reconcile_toner_alerts(
            [cylinder],
            [toner(18)],
            printer_model=None,
        )

        self.assertIn(cylinder, alerts)
        self.assertIn("toner_percentual_baixo", [alert["codigo"] for alert in alerts])

    def test_multiplos_toners_geram_alertas_por_cor(self):
        alerts = toner_percentage_alerts(
            [toner(45), toner(19, cor="cyan"), toner(8, cor="magenta"), toner(70, cor="yellow")],
            thresholds=TonerThresholds(),
        )

        self.assertEqual(
            [(alert["codigo"], alert["severidade"]) for alert in alerts],
            [
                ("toner_percentual_baixo", "medium"),
                ("toner_percentual_critico", "high"),
            ],
        )

    def test_multiplos_toners_criticos_permanecem_alternaveis(self):
        alerts = toner_percentage_alerts(
            [toner(8), toner(9, cor="magenta")],
            thresholds=TonerThresholds(),
        )

        self.assertEqual(len(alerts), 2)
        self.assertTrue(all(alert["severidade"] == "high" for alert in alerts))

    def test_threshold_configurado_no_modelo_sobrescreve_padrao(self):
        model = SimpleNamespace(critical_toner_threshold=5, low_toner_threshold=15)
        thresholds = resolve_toner_thresholds(model)
        alerts = toner_percentage_alerts([toner(10)], thresholds=thresholds)

        self.assertEqual((thresholds.critical, thresholds.low), (5, 15))
        self.assertEqual(alerts[0]["severidade"], "medium")

    def test_configuracao_ausente_usa_fallback_global(self):
        model = SimpleNamespace(critical_toner_threshold=None, low_toner_threshold=None)

        self.assertEqual(resolve_toner_thresholds(model), TonerThresholds(10, 20))

    def test_configuracao_invalida_usa_fallback_global(self):
        model = SimpleNamespace(critical_toner_threshold=30, low_toner_threshold=20)

        self.assertEqual(resolve_toner_thresholds(model), TonerThresholds(10, 20))
