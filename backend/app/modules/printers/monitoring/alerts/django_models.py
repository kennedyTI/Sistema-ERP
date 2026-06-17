"""Espelhos Django unmanaged dos alertas persistidos."""

from django.db import models

from backend.app.modules.printers.machines.django_models import PrinterMachineAdminModel
from backend.app.modules.printers.monitoring.snmp.django_models import (
    PrinterSnmpOidAdminModel,
)
from backend.app.modules.printers.monitoring.state.django_models import (
    PrinterAlertRuleAdminModel,
)


class PrinterCurrentAlertAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    maquina = models.ForeignKey(
        PrinterMachineAdminModel,
        verbose_name="IMPRESSORA",
        db_column="maquina_id",
        on_delete=models.DO_NOTHING,
    )
    regra_alerta = models.ForeignKey(
        PrinterAlertRuleAdminModel,
        verbose_name="REGRA",
        db_column="regra_alerta_id",
        on_delete=models.DO_NOTHING,
    )
    oid_snmp = models.ForeignKey(
        PrinterSnmpOidAdminModel,
        verbose_name="OID SNMP",
        db_column="oid_snmp_id",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )
    mensagem_original = models.TextField("MENSAGEM ORIGINAL", null=True, blank=True)
    mensagem_original_normalizada = models.CharField(
        "MENSAGEM NORMALIZADA",
        max_length=1000,
        null=True,
        blank=True,
    )
    origem_coleta = models.CharField("ORIGEM COLETA", max_length=20)
    metodo_confirmacao = models.CharField("METODO CONFIRMACAO", max_length=30)
    metodo_coleta = models.CharField("METODO COLETA", max_length=30)
    oid_retornado = models.CharField("OID RETORNADO", max_length=255, null=True, blank=True)
    chave_alerta = models.CharField("CHAVE ALERTA", max_length=500)
    verificado_em = models.DateTimeField("VERIFICADO EM")
    criado_em = models.DateTimeField("CRIADO EM")
    atualizado_em = models.DateTimeField("ATUALIZADO EM")

    class Meta:
        app_label = "printer_machines"
        managed = False
        db_table = "alertas_impressoras"
        verbose_name = "ALERTA_IMPRESSORA"
        verbose_name_plural = "ALERTAS_IMPRESSORAS"
        unique_together = (("maquina", "chave_alerta"),)

    def __str__(self):
        return f"{self.maquina} - {self.chave_alerta}"


class PrinterAlertHistoryAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    maquina = models.ForeignKey(
        PrinterMachineAdminModel,
        verbose_name="IMPRESSORA",
        db_column="maquina_id",
        on_delete=models.DO_NOTHING,
    )
    regra_alerta = models.ForeignKey(
        PrinterAlertRuleAdminModel,
        verbose_name="REGRA",
        db_column="regra_alerta_id",
        on_delete=models.DO_NOTHING,
    )
    oid_snmp = models.ForeignKey(
        PrinterSnmpOidAdminModel,
        verbose_name="OID SNMP",
        db_column="oid_snmp_id",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )
    codigo_alerta = models.CharField("CODIGO ALERTA", max_length=60)
    severidade = models.CharField("SEVERIDADE", max_length=20)
    classificacao_anterior = models.CharField("CLASSIFICACAO ANTERIOR", max_length=20)
    classificacao_nova = models.CharField("CLASSIFICACAO NOVA", max_length=20)
    origem_coleta = models.CharField("ORIGEM COLETA", max_length=20)
    metodo_confirmacao = models.CharField("METODO CONFIRMACAO", max_length=30)
    metodo_coleta = models.CharField("METODO COLETA", max_length=30)
    oid_retornado = models.CharField("OID RETORNADO", max_length=255, null=True, blank=True)
    chave_alerta = models.CharField("CHAVE ALERTA", max_length=500)
    mensagem_original = models.TextField("MENSAGEM ORIGINAL", null=True, blank=True)
    mensagem_original_normalizada = models.CharField(
        "MENSAGEM NORMALIZADA",
        max_length=1000,
        null=True,
        blank=True,
    )
    codigo_evento = models.CharField("CODIGO EVENTO", max_length=40)
    descricao_evento = models.CharField("DESCRICAO EVENTO", max_length=255)
    detalhes = models.JSONField("DETALHES")
    verificado_em = models.DateTimeField("VERIFICADO EM")
    criado_em = models.DateTimeField("CRIADO EM")

    class Meta:
        app_label = "printer_machines"
        managed = False
        db_table = "historico_alertas_impressoras"
        verbose_name = "HISTORICO_ALERTA_IMPRESSORA"
        verbose_name_plural = "HISTORICO_ALERTAS_IMPRESSORAS"

    def __str__(self):
        return f"{self.maquina} - {self.codigo_evento}"
