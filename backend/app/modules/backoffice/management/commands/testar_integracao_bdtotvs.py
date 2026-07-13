"""Comando sanitizado de healthcheck da integracao bdTotvs."""

from django.core.management.base import BaseCommand, CommandError

from backend.app.modules.integracoes.bdTotvs.config import (
    format_presence_report,
    get_totvs_db_config,
    get_totvs_env_presence,
)
from backend.app.modules.integracoes.bdTotvs.exceptions import TotvsIntegrationError
from backend.app.modules.integracoes.bdTotvs.healthcheck import test_connection


class Command(BaseCommand):
    help = "Testa a integracao bdTotvs com SELECT 1 AS ok"

    def handle(self, *args, **options):
        try:
            config = get_totvs_db_config()
        except TotvsIntegrationError as exc:
            presence = get_totvs_env_presence()
            self.stdout.write(
                "[bdTotvs] Configuracao carregada: "
                f"{format_presence_report(presence)}."
            )
            self.stdout.write(
                f"[bdTotvs] Falha ao conectar ao bdTotvs. Codigo: {exc.error_code}."
            )
            raise CommandError("Falha ao validar bdTotvs.") from exc

        self.stdout.write(
            "[bdTotvs] Configuracao carregada: "
            f"{format_presence_report(config.presence_report())}."
        )

        result = test_connection(config=config)
        if result.success:
            self.stdout.write("[bdTotvs] Teste SELECT 1 executado com sucesso.")
            self.stdout.write(f"[bdTotvs] Tempo: {result.elapsed_ms}ms.")
            return

        self.stdout.write(
            "[bdTotvs] Falha ao conectar ao bdTotvs. "
            f"Codigo: {result.error_code or 'integration_error'}."
        )
        self.stdout.write(f"[bdTotvs] Tempo: {result.elapsed_ms}ms.")
        raise CommandError("Falha ao validar bdTotvs.")
