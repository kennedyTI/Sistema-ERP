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
            "frontend/src/shared/ui",
            "frontend/src/shared/lib",
        )

        missing = [path for path in expected_paths if not (PROJECT_ROOT / path).exists()]
        self.assertEqual(missing, [])
