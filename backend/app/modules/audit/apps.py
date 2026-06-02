"""
App Django para expor logs/auditoria genericos no Admin.
"""

from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.app.modules.audit"
    label = "audit"
    verbose_name = "Auditoria"
