"""App Django da configuracao SNMP/OIDs de impressoras."""

from django.apps import AppConfig


class PrinterSnmpOidsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.app.modules.printers.monitoring.snmp"
    label = "printer_snmp_oids"
    verbose_name = "OIDs SNMP de impressoras"
