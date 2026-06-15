"""Espelho Django unmanaged das regras de alertas de impressoras."""

from django.db import models


class PrinterAlertRuleAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    codigo = models.CharField("CODIGO", max_length=60, unique=True)
    descricao = models.CharField("DESCRICAO", max_length=255)
    severidade = models.CharField(
        "SEVERIDADE",
        max_length=20,
        choices=(
            ("green", "Green"),
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ),
    )
    tipo_regra = models.CharField(
        "TIPO DE REGRA",
        max_length=20,
        choices=(
            ("contains", "Contains"),
            ("equals", "Equals"),
            ("regex", "Regex"),
        ),
    )
    padrao = models.CharField("PADRAO", max_length=1000, blank=True)
    prioridade = models.IntegerField("PRIORIDADE")
    ativo = models.BooleanField("ATIVO", default=True)
    criado_em = models.DateTimeField("CRIADO EM")
    atualizado_em = models.DateTimeField("ATUALIZADO EM")

    class Meta:
        app_label = "printer_alert_rules"
        managed = False
        db_table = "regras_alertas_impressoras"
        verbose_name = "Regra de alerta de impressora"
        verbose_name_plural = "Regras de alertas de impressoras"

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"
