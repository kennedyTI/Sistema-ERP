"""App Django para expor maquinas no Admin."""

from django.apps import AppConfig


class PrinterMachinesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.app.modules.printers.machines"
    label = "printer_machines"
    verbose_name = "Impressoras - Maquinas"
