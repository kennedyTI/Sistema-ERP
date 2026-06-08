"""Models Django unmanaged para exposicao no Admin."""

from django.db import models


class PrinterModelAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    manufacturer = models.CharField("FABRICANTE", max_length=120)
    name = models.CharField("MODELO", max_length=120)
    type = models.CharField("TIPO", max_length=80, null=True, blank=True)
    color_mode = models.CharField("COR_MODELO", max_length=40, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "printer_machines"
        managed = False
        db_table = "printers_models"
        verbose_name = "Modelo de impressora"
        verbose_name_plural = "Modelos de impressora"
        unique_together = (("manufacturer", "name"),)

    def __str__(self):
        return f"{self.manufacturer} {self.name}"


class PrinterMachineAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=160)
    ip_address = models.CharField(max_length=45, unique=True)
    printer_model = models.ForeignKey(
        PrinterModelAdminModel,
        db_column="model_id",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="machines",
    )
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
        verbose_name = "Impressora"
        verbose_name_plural = "Impressoras"

    def __str__(self):
        return f"{self.name} ({self.ip_address})"
