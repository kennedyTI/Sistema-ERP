"""App Django da automacao de novo usuario Windows."""

from django.apps import AppConfig


class AutomacaoNovoUsuarioConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.app.modules.automacao.novo_usuario"
    label = "automacao_novo_usuario"
    verbose_name = "Automacao de novo usuario Windows"
