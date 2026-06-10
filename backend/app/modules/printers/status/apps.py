"""App Django para status e logs operacionais de impressoras."""

from django.apps import AppConfig


class PrinterStatusConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.app.modules.printers.status"
    label = "printer_status"
    verbose_name = "Status de impressoras"
