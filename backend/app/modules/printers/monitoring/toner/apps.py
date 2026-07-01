"""App Django do toner de impressoras."""

from django.apps import AppConfig


class PrinterTonerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.app.modules.printers.monitoring.toner"
    label = "printer_toner"
    verbose_name = "Impressoras"
