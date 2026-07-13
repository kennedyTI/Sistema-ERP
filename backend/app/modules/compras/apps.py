"""App Django que centraliza permissoes funcionais de Compras."""

from django.apps import AppConfig


class ComprasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.app.modules.compras"
    label = "compras"
    verbose_name = "Permissoes de Compras"
