"""Espelhos Django unmanaged do toner das impressoras."""

from django.db import models

from backend.app.modules.printers.machines.django_models import PrinterMachineAdminModel


class PrinterTonerStatusAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    maquina = models.ForeignKey(
        PrinterMachineAdminModel,
        verbose_name="IMPRESSORA",
        db_column="maquina_id",
        on_delete=models.DO_NOTHING,
    )
    cor = models.CharField("COR", max_length=20)
    indice_suprimento = models.CharField("INDICE SUPRIMENTO", max_length=80)
    descricao_coletada = models.CharField("DESCRICAO COLETADA", max_length=255, null=True, blank=True)
    tipo_suprimento = models.CharField("TIPO SUPRIMENTO", max_length=80, null=True, blank=True)
    unidade_suprimento = models.CharField("UNIDADE SUPRIMENTO", max_length=80, null=True, blank=True)
    nivel_atual = models.FloatField("NIVEL ATUAL", null=True, blank=True)
    capacidade_maxima = models.FloatField("CAPACIDADE MAXIMA", null=True, blank=True)
    percentual = models.IntegerField("PERCENTUAL", null=True, blank=True)
    origem_coleta = models.CharField("ORIGEM COLETA", max_length=20)
    metodo_coleta = models.CharField("METODO COLETA", max_length=40)
    sucesso = models.BooleanField("SUCESSO")
    erro_codigo = models.CharField("ERRO CODIGO", max_length=80, null=True, blank=True)
    erro_detalhe = models.TextField("ERRO DETALHE", null=True, blank=True)
    coletado_em = models.DateTimeField("COLETADO EM")
    criado_em = models.DateTimeField("CRIADO EM")
    atualizado_em = models.DateTimeField("ATUALIZADO EM")

    class Meta:
        app_label = "printer_toner"
        managed = False
        db_table = "status_toner_impressoras"
        verbose_name = "status_toner_impressora"
        verbose_name_plural = "status_toner_impressoras"
        unique_together = (("maquina", "cor", "indice_suprimento"),)

    def __str__(self):
        return f"{self.maquina} - {self.cor}"


class PrinterTonerHistoryAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    maquina = models.ForeignKey(
        PrinterMachineAdminModel,
        verbose_name="IMPRESSORA",
        db_column="maquina_id",
        on_delete=models.DO_NOTHING,
    )
    status_toner = models.ForeignKey(
        PrinterTonerStatusAdminModel,
        verbose_name="STATUS TONER",
        db_column="status_toner_id",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )
    cor = models.CharField("COR", max_length=20)
    indice_suprimento = models.CharField("INDICE SUPRIMENTO", max_length=80)
    percentual_anterior = models.IntegerField("PERCENTUAL ANTERIOR", null=True, blank=True)
    percentual_novo = models.IntegerField("PERCENTUAL NOVO", null=True, blank=True)
    erro_codigo_anterior = models.CharField("ERRO ANTERIOR", max_length=80, null=True, blank=True)
    erro_codigo_novo = models.CharField("ERRO NOVO", max_length=80, null=True, blank=True)
    codigo_evento = models.CharField("CODIGO EVENTO", max_length=40)
    descricao_evento = models.CharField("DESCRICAO EVENTO", max_length=255)
    origem_coleta = models.CharField("ORIGEM COLETA", max_length=20)
    metodo_coleta = models.CharField("METODO COLETA", max_length=40)
    coletado_em = models.DateTimeField("COLETADO EM")
    criado_em = models.DateTimeField("CRIADO EM")

    class Meta:
        app_label = "printer_toner"
        managed = False
        db_table = "historico_toner_impressoras"
        verbose_name = "historico_toner_impressora"
        verbose_name_plural = "historico_toner_impressoras"

    def __str__(self):
        return f"{self.maquina} - {self.cor} - {self.codigo_evento}"
