"""Models Django unmanaged para exposicao no Admin."""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PrinterModelAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    manufacturer = models.CharField("FABRICANTE", max_length=120)
    name = models.CharField("MODELO", max_length=120)
    type = models.CharField("TIPO", max_length=80, null=True, blank=True)
    color_mode = models.CharField("COR_MODELO", max_length=40, null=True, blank=True)
    url_imagem = models.CharField("URL DA IMAGEM", max_length=500, null=True, blank=True)
    critical_toner_threshold = models.IntegerField(
        "LIMITE TONER CRITICO",
        db_column="limite_toner_critico",
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Padrao global quando vazio: 10%.",
    )
    low_toner_threshold = models.IntegerField(
        "LIMITE TONER BAIXO",
        db_column="limite_toner_baixo",
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Padrao global quando vazio: 20%.",
    )
    notes = models.TextField("OBSERVACOES", null=True, blank=True)
    created_at = models.DateTimeField("CRIADO EM", null=True, blank=True)
    updated_at = models.DateTimeField("ATUALIZADO EM", null=True, blank=True)

    class Meta:
        app_label = "printer_machines"
        managed = False
        db_table = "printers_models"
        verbose_name = "Modelo de impressora"
        verbose_name_plural = "Modelos de impressora"
        unique_together = (("manufacturer", "name"),)

    def __str__(self):
        return f"{self.manufacturer} {self.name}"

    def clean(self):
        super().clean()
        if (
            self.critical_toner_threshold is not None
            and self.low_toner_threshold is not None
            and self.critical_toner_threshold > self.low_toner_threshold
        ):
            raise ValidationError(
                {
                    "critical_toner_threshold": (
                        "O limite critico deve ser menor ou igual ao limite baixo."
                    )
                }
            )


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
