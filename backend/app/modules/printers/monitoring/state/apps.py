"""Configuracao Django das regras de alertas de impressoras."""

from django.apps import AppConfig


class PrinterAlertRulesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.app.modules.printers.monitoring.state"
    label = "printer_alert_rules"
    verbose_name = "Configuracao de impressoras"
