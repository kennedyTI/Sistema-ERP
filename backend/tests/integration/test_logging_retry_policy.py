from pathlib import Path
from unittest import TestCase

from backend.app.core.logging import StructuredJsonFormatter, configure_logging

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PYTHON_FILES_TO_SCAN = [
    path
    for base in (PROJECT_ROOT / "backend", PROJECT_ROOT / "docker")
    for path in base.rglob("*.py")
    if "__pycache__" not in path.parts
]


class LoggingPolicyTest(TestCase):
    def test_configuracao_central_de_logging_existe(self):
        configure_logging()
        self.assertTrue(callable(configure_logging))
        self.assertTrue(callable(StructuredJsonFormatter))

    def test_codigo_nao_usa_print_operacional(self):
        offenders = []
        for path in PYTHON_FILES_TO_SCAN:
            if path.name == "test_logging_retry_policy.py":
                continue
            text = path.read_text(encoding="utf-8")
            if "print(" in text:
                offenders.append(str(path.relative_to(PROJECT_ROOT)))

        self.assertEqual(offenders, [])

    def test_dependencias_de_monitoramento_foram_declaradas(self):
        requirements = (PROJECT_ROOT / "backend/requirements.txt").read_text(encoding="utf-8")

        for dependency in ("pysnmp", "pyasn1", "celery", "redis"):
            with self.subTest(dependency=dependency):
                self.assertIn(dependency, requirements)

