"""Espelho Django unmanaged da configuracao de OIDs SNMP."""

from django.db import models

from backend.app.modules.printers.machines.django_models import PrinterModelAdminModel


class PrinterSnmpOidAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    modelo = models.ForeignKey(
        PrinterModelAdminModel,
        verbose_name="MODELO",
        db_column="modelo_id",
        on_delete=models.DO_NOTHING,
        related_name="oids_snmp",
    )
    chave_metrica = models.CharField(
        "CHAVE METRICA",
        max_length=80,
        choices=(
            ("alert_raw", "alert_raw"),
            ("name", "name"),
            ("location", "location"),
            ("page_count_total", "page_count_total"),
        ),
    )
    oid = models.CharField("OID", max_length=255)
    tipo_valor = models.CharField(
        "TIPO VALOR",
        max_length=30,
        choices=(
            ("string", "string"),
            ("integer", "integer"),
            ("counter", "counter"),
            ("gauge", "gauge"),
            ("boolean", "boolean"),
        ),
    )
    versao_snmp = models.CharField(
        "VERSAO SNMP",
        max_length=10,
        choices=(("1", "1"), ("2c", "2c")),
    )
    modo_consulta = models.CharField(
        "MODO CONSULTA",
        max_length=10,
        choices=(("get", "get"), ("walk", "walk")),
    )
    ativo = models.BooleanField("ATIVO", default=True)
    criado_em = models.DateTimeField("CRIADO EM")
    atualizado_em = models.DateTimeField("ATUALIZADO EM")

    class Meta:
        app_label = "printer_machines"
        managed = False
        db_table = "oids_snmp_impressoras"
        verbose_name = "OID_SNMP_IMPRESSORA"
        verbose_name_plural = "OIDs_SNMP_IMPRESSORAS"
        unique_together = (("modelo", "chave_metrica"),)

    def __str__(self):
        return f"{self.modelo} - {self.chave_metrica}"
