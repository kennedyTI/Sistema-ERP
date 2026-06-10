"""App Django que centraliza as permissoes funcionais de Impressoras."""

from django.apps import AppConfig


class PrintersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.app.modules.printers"
    label = "impressoras"
    verbose_name = "Permissoes de Impressoras"
