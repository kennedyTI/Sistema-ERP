"""App Django dos alertas persistidos de impressoras."""

from django.apps import AppConfig


class PrinterAlertsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.app.modules.printers.monitoring.alerts"
    label = "printer_alerts"
    verbose_name = "Impressoras"
