"""
App Django para comandos e politicas gerais do backoffice.
"""

from django.apps import AppConfig


class BackofficeModuleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.app.modules.backoffice"
    label = "portal_backoffice"
    verbose_name = "Backoffice"
