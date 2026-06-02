from datetime import datetime
from pathlib import Path
from unittest import TestCase
from zoneinfo import ZoneInfo

from backend.app.core.timezone import SAO_PAULO_TIME_ZONE, now_sao_paulo
from backend.app.modules.audit.orm import Log
from backend.backoffice import settings as django_settings


class TimezonePolicyTest(TestCase):
    def test_now_sao_paulo_retorna_horario_local_naive(self):
        expected = datetime.now(ZoneInfo(SAO_PAULO_TIME_ZONE)).replace(tzinfo=None)
        current = now_sao_paulo()

        self.assertIsNone(current.tzinfo)
        self.assertLess(abs((expected - current).total_seconds()), 2)

    def test_models_services_principais_nao_usam_utcnow(self):
        root = Path(__file__).resolve().parents[3]
        checked_dirs = (
            root / "backend" / "app" / "modules",
            root / "backend" / "app" / "core",
        )

        offenders = []
        for checked_dir in checked_dirs:
            for file_path in checked_dir.rglob("*.py"):
                if file_path.name == "timezone.py":
                    continue
                text = file_path.read_text(encoding="utf-8")
                if "datetime.utcnow" in text:
                    offenders.append(str(file_path.relative_to(root)))

        self.assertEqual(offenders, [])

    def test_logs_created_at_usa_timezone_local(self):
        created_default = Log.__table__.c.created_at.default.arg

        self.assertEqual(created_default.__name__, now_sao_paulo.__name__)
        self.assertLess(abs((now_sao_paulo() - created_default(None)).total_seconds()), 2)

    def test_django_usa_timezone_de_sao_paulo_sem_utc(self):
        self.assertEqual(django_settings.TIME_ZONE, SAO_PAULO_TIME_ZONE)
        self.assertFalse(django_settings.USE_TZ)

