from datetime import datetime
from unittest import TestCase

from backend.app.modules.printers.monitoring.config import MonitoringSettings
from backend.pyteste import diagnostico_snmp_alertas as diagnostic


class FakeSnmpValue:
    def __init__(self, value: bytes | str):
        self.value = value

    def prettyPrint(self):
        if isinstance(self.value, bytes):
            return self.value.decode("latin1", errors="replace")
        return str(self.value)

    def asOctets(self):
        if isinstance(self.value, bytes):
            return self.value
        return str(self.value).encode("utf-8")

    def __repr__(self):
        return f"FakeSnmpValue({self.value!r})"


def candidate(
    *,
    model_id=1,
    manufacturer="Brother",
    model="DCP-L1632W",
    machine_id=10,
    machine="IMP-001",
    ip="192.0.2.10",
    active=True,
):
    return {
        "modelo_id": model_id,
        "fabricante": manufacturer,
        "modelo": model,
        "oid_alert_raw": "1.3.6.1.2.1.43.18.1.1.8.1.1",
        "tipo_valor": "string",
        "versao_snmp": "2c",
        "maquina_id": machine_id,
        "maquina": machine,
        "ip": ip,
        "maquina_ativa": active,
        "status_previo": "online",
    }


def settings(community="community-teste"):
    return MonitoringSettings(snmp_community=community)


class SnmpAlertDiagnosticTest(TestCase):
    def test_script_nao_executa_coleta_real_sem_confirmar(self):
        calls = {"online": 0, "get": 0, "walk": 0}

        def online_checker(_target, _settings):
            calls["online"] += 1
            return {"online": True}

        def snmp_get(**_kwargs):
            calls["get"] += 1
            return {}

        def snmp_walk(**_kwargs):
            calls["walk"] += 1
            return {}

        targets = diagnostic.select_diagnostic_targets([candidate()])
        report = diagnostic.build_report(
            targets=targets,
            confirmar=False,
            settings=settings(),
            connectivity_checker=online_checker,
            snmp_get=snmp_get,
            snmp_walk=snmp_walk,
            timestamp=datetime(2026, 6, 16, 10, 0, 0),
        )

        self.assertFalse(report["executado"])
        self.assertEqual(calls, {"online": 0, "get": 0, "walk": 0})

    def test_selecao_escolhe_uma_maquina_ativa_por_modelo(self):
        targets = diagnostic.select_diagnostic_targets(
            [
                candidate(machine_id=12, machine="IMP-012", ip="192.0.2.12"),
                candidate(machine_id=10, machine="IMP-010", ip="192.0.2.10"),
            ]
        )

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].maquina_id, 10)

    def test_modelo_sem_maquina_ativa_e_registrado_como_ignorado(self):
        row = candidate(machine_id=None, machine=None, ip=None, active=False)

        targets = diagnostic.select_diagnostic_targets([row])

        self.assertEqual(targets[0].motivo_ignorado, "sem_maquina_ativa")

    def test_maquina_offline_e_registrada_como_ignorada(self):
        calls = {"get": 0, "walk": 0}

        def snmp_get(**_kwargs):
            calls["get"] += 1
            return {}

        def snmp_walk(**_kwargs):
            calls["walk"] += 1
            return {}

        result = diagnostic.diagnose_target(
            diagnostic.select_diagnostic_targets([candidate()])[0],
            settings=settings(),
            connectivity_checker=lambda _target, _settings: {
                "online": False,
                "motivo": "offline",
            },
            snmp_get=snmp_get,
            snmp_walk=snmp_walk,
        )

        self.assertEqual(result["motivo_ignorado"], "maquina_offline")
        self.assertEqual(result["conclusao_preliminar"], "Modelo sem maquina online")
        self.assertEqual(calls, {"get": 0, "walk": 0})

    def test_resultado_get_e_serializado_em_formato_bruto(self):
        result = diagnostic.build_get_result(
            oid="1.3.6.1.2.1.43.18.1.1.8.1.1",
            value=FakeSnmpValue(b"Pronta"),
            latency_ms=3,
        )

        self.assertTrue(result["sucesso"])
        self.assertEqual(result["quantidade_valores"], 1)
        self.assertEqual(result["valor_bruto"]["valor_bytes_hex"], "50726f6e7461")
        self.assertEqual(result["valor_bruto"]["decodificacao_utf8"], "Pronta")

    def test_resultado_walk_com_multiplos_oids_e_serializado_em_lista(self):
        result = diagnostic.build_walk_result(
            base_oid="1.3.6.1.2.1.43.18.1.1.8",
            nome="prtAlertDescription",
            values=[
                ("1.3.6.1.2.1.43.18.1.1.8.1.1", FakeSnmpValue("Ready")),
                ("1.3.6.1.2.1.43.18.1.1.8.1.2", FakeSnmpValue("Cover open")),
            ],
        )

        self.assertEqual(result["quantidade_retornada"], 2)
        self.assertEqual(
            [item["oid_retornado"] for item in result["valores"]],
            [
                "1.3.6.1.2.1.43.18.1.1.8.1.1",
                "1.3.6.1.2.1.43.18.1.1.8.1.2",
            ],
        )

    def test_community_nao_aparece_no_json(self):
        community = "segredo-snmp"
        report = diagnostic.sanitize_sensitive_data(
            {
                "erro": f"falha usando {community}",
                "community": community,
                "aninhado": [{"texto": community}],
            },
            community,
        )

        serialized = str(report)
        self.assertNotIn(community, serialized)
        self.assertNotIn("community", report)

    def test_community_nao_aparece_no_markdown(self):
        community = "segredo-snmp"
        report = diagnostic.sanitize_sensitive_data(
            {
                "executado": False,
                "modo": "dry_run",
                "gerado_em": "2026-06-16T10:00:00",
                "alvos_planejados": [
                    {
                        "fabricante": "Brother",
                        "modelo": "DCP-L1632W",
                        "maquina": f"sem {community}",
                        "ip": "192.0.2.10",
                        "motivo_ignorado": None,
                    }
                ],
            },
            community,
        )

        markdown = diagnostic.build_markdown(report)

        self.assertNotIn(community, markdown)

    def test_conclusao_get_suficiente_quando_get_e_walk_tem_um_valor(self):
        get_result = diagnostic.build_get_result(
            oid="1.3.6.1.2.1.43.18.1.1.8.1.1",
            value=FakeSnmpValue("Ready"),
        )
        walk_result = diagnostic.build_walk_result(
            base_oid="1.3.6.1.2.1.43.18.1.1.8",
            nome="prtAlertDescription",
            values=[("1.3.6.1.2.1.43.18.1.1.8.1.1", FakeSnmpValue("Ready"))],
        )

        self.assertEqual(
            diagnostic.preliminary_conclusion(get_result, [walk_result]),
            "GET suficiente",
        )

    def test_conclusao_walk_necessario_quando_walk_tem_multiplos_valores(self):
        get_result = diagnostic.build_get_result(
            oid="1.3.6.1.2.1.43.18.1.1.8.1.1",
            value=FakeSnmpValue("Ready"),
        )
        walk_result = diagnostic.build_walk_result(
            base_oid="1.3.6.1.2.1.43.18.1.1.8",
            nome="prtAlertDescription",
            values=[
                ("1.3.6.1.2.1.43.18.1.1.8.1.1", FakeSnmpValue("Ready")),
                ("1.3.6.1.2.1.43.18.1.1.8.1.2", FakeSnmpValue("Cover open")),
            ],
        )

        self.assertEqual(
            diagnostic.preliminary_conclusion(get_result, [walk_result]),
            "WALK necessario para multiplos alertas",
        )
