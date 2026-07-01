from pathlib import Path
from unittest import TestCase


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class CleanBasePolicyTest(TestCase):
    def test_backend_nao_mantem_arquivos_legados_de_impressoras(self):
        forbidden_paths = (
            "backend/app/tasks/printer_tasks.py",
            "backend/app/api/v1/frontend_dashboard.py",
            "backend/app/api/v1/paper.py",
            "backend/app/api/v1/protheus.py",
            "backend/scripts/seed_printers.py",
            "backend/scripts/seed_snmp_oids.py",
            "backend/scripts/seed_supplies.py",
            "backend/scripts/validate_toner_oids.py",
        )

        existing = [path for path in forbidden_paths if (PROJECT_ROOT / path).exists()]
        self.assertEqual(existing, [])

    def test_backend_modular_possui_pastas_base(self):
        expected_paths = (
            "backend/app/core",
            "backend/app/modules/auth",
            "backend/app/modules/backoffice",
            "backend/app/modules/audit",
            "backend/app/modules/printers/dashboard",
            "backend/app/modules/printers/machines",
            "backend/app/modules/printers/paper",
            "backend/app/modules/printers/status",
            "backend/app/shared",
            "backend/app/migrations/versions",
            "backend/backoffice/settings.py",
        )

        missing = [path for path in expected_paths if not (PROJECT_ROOT / path).exists()]
        self.assertEqual(missing, [])

    def test_frontend_nao_mantem_rotas_legadas(self):
        forbidden_paths = (
            "frontend/src/routes/dashboard.tsx",
            "frontend/src/routes/printers.tsx",
            "frontend/src/routes/paper.tsx",
            "frontend/src/components/dashboard",
        )

        existing = [path for path in forbidden_paths if (PROJECT_ROOT / path).exists()]
        self.assertEqual(existing, [])

    def test_frontend_modular_possui_pastas_base(self):
        expected_paths = (
            "frontend/src/app/router.tsx",
            "frontend/src/app/providers.tsx",
            "frontend/src/app/layout/AppLayout.tsx",
            "frontend/src/app/layout/Sidebar.tsx",
            "frontend/src/modules/auth/LoginPage.tsx",
            "frontend/src/modules/home/HomePage.tsx",
            "frontend/src/modules/printers/dashboard/DashboardPage.tsx",
            "frontend/src/modules/printers/machines/MachinesPage.tsx",
            "frontend/src/modules/printers/paper/PaperPage.tsx",
            "frontend/src/modules/printers/status/StatusPage.tsx",
            "frontend/src/shared/ui",
            "frontend/src/shared/lib",
        )

        missing = [path for path in expected_paths if not (PROJECT_ROOT / path).exists()]
        self.assertEqual(missing, [])

    def test_central_de_operacao_mantem_contrato_visual_da_etapa(self):
        status_page = (
            PROJECT_ROOT / "frontend/src/modules/printers/status/StatusPage.tsx"
        ).read_text(encoding="utf-8")
        details_dialog = (
            PROJECT_ROOT
            / "frontend/src/modules/printers/status/components/StatusDetailsDialog.tsx"
        ).read_text(encoding="utf-8")
        summary_cards = (
            PROJECT_ROOT
            / "frontend/src/modules/printers/status/components/StatusSummaryCards.tsx"
        ).read_text(encoding="utf-8")

        default_order = status_page.split("const DEFAULT_COLUMN_ORDER", 1)[1].split("];", 1)[0]
        expected_columns = (
            '"status"',
            '"alert"',
            '"location"',
            '"machine"',
            '"model"',
            '"ip"',
            '"updatedAt"',
        )
        positions = [default_order.index(column) for column in expected_columns]

        self.assertEqual(positions, sorted(positions))
        self.assertIn("StatusSummaryCards", status_page)
        self.assertIn("StatusDetailsDialog", status_page)
        self.assertIn("onPointerDown", status_page)
        self.assertIn("onPointerMove", status_page)
        self.assertIn("localStorage.setItem", status_page)
        self.assertIn("renderStatusCell", status_page)
        self.assertIn("STATUS_REFRESH_INTERVAL_MS", status_page)
        self.assertIn("setInterval", status_page)
        self.assertIn("clearInterval", status_page)
        self.assertIn("modelo_exibicao", status_page)
        self.assertIn("sticky top-0", status_page)
        self.assertNotIn("Status operacional", status_page)
        self.assertNotIn("alertLabels", status_page)
        self.assertNotIn("<TableHead>Resposta</TableHead>", status_page)
        self.assertNotIn("Copiar IP", status_page + details_dialog)
        self.assertNotIn("Solicitar toner", status_page + details_dialog)
        self.assertNotIn("Resposta técnica", details_dialog)
        self.assertNotIn("resposta_bruta", details_dialog)
        self.assertIn("Últimos logs das últimas 24h", details_dialog)
        self.assertIn("Última verificação", details_dialog)
        self.assertIn(
            "Nenhum evento operacional registrado nas últimas 24h.",
            details_dialog,
        )
        self.assertIn("url_imagem", details_dialog)
        self.assertNotIn('"/static/imgs/printers"', details_dialog)
        self.assertIn("PrinterModelImage", details_dialog)
        self.assertIn("Droplet", summary_cards)
        self.assertNotIn("PackageSearch", summary_cards)

    def test_telas_operacionais_mantem_cards_primeiro_e_modais_responsivos(self):
        machines_page = (
            PROJECT_ROOT / "frontend/src/modules/printers/machines/MachinesPage.tsx"
        ).read_text(encoding="utf-8")
        status_page = (
            PROJECT_ROOT / "frontend/src/modules/printers/status/StatusPage.tsx"
        ).read_text(encoding="utf-8")
        machine_dialog = (
            PROJECT_ROOT
            / "frontend/src/modules/printers/machines/components/MachineDetailsDialog.tsx"
        ).read_text(encoding="utf-8")
        status_dialog = (
            PROJECT_ROOT
            / "frontend/src/modules/printers/status/components/StatusDetailsDialog.tsx"
        ).read_text(encoding="utf-8")
        model_image = (
            PROJECT_ROOT / "frontend/src/modules/printers/shared/PrinterModelImage.tsx"
        ).read_text(encoding="utf-8")

        self.assertLess(
            machines_page.index("<MachinesSummaryCards"),
            machines_page.index("<Table"),
        )
        self.assertLess(
            status_page.index("<StatusSummaryCards"),
            status_page.index("<Table"),
        )
        self.assertNotIn("Atualizar", machines_page)
        self.assertNotIn("Atualizar", status_page)
        self.assertNotIn("<h1", machines_page)
        self.assertNotIn("<h1", status_page)
        self.assertIn("92dvh", machine_dialog)
        self.assertIn("92dvh", status_dialog)
        self.assertIn("280px", machine_dialog)
        self.assertIn("280px", status_dialog)
        self.assertIn("Imagem não disponível", model_image)
        self.assertIn("object-contain", model_image)

    def test_backend_de_maquinas_mantem_contratos_em_portugues(self):
        schemas = (
            PROJECT_ROOT / "backend/app/modules/printers/machines/schemas.py"
        ).read_text(encoding="utf-8")
        api = (
            PROJECT_ROOT / "backend/app/modules/printers/machines/api.py"
        ).read_text(encoding="utf-8")
        migration = (
            PROJECT_ROOT
            / "backend/app/migrations/versions/20260610_maquinas_backend.py"
        ).read_text(encoding="utf-8")

        for field in (
            "nome",
            "endereco_ip",
            "centro_custo",
            "ativo",
            "criado_em",
            "atualizado_em",
            "url_imagem",
        ):
            self.assertIn(field, schemas)
        self.assertIn('"/summary"', api)
        self.assertIn('"/{machine_id}/details"', api)
        self.assertIn("url_imagem", migration)
