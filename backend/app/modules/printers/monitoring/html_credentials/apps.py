"""App Django das credenciais de coleta HTML de impressoras."""

from django.apps import AppConfig


class PrinterHtmlCredentialsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.app.modules.printers.monitoring.html_credentials"
    label = "printer_html_credentials"
    verbose_name = "Impressoras"

