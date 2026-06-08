"""Models Django unmanaged para exposicao no Admin."""

from django.db import models


class PrinterMachineAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=160)
    ip_address = models.CharField(max_length=45, unique=True)
    manufacturer = models.CharField(max_length=120, null=True, blank=True)
    model = models.CharField(max_length=120, null=True, blank=True)
    sector = models.CharField(max_length=120, null=True, blank=True)
    cost_center = models.CharField(max_length=80, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "printer_machines"
        managed = False
        db_table = "printer_machines"
        verbose_name = "Maquina"
        verbose_name_plural = "Maquinas"

    def __str__(self):
        return f"{self.name} ({self.ip_address})"
