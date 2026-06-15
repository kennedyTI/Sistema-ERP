"""Models Django unmanaged para o Admin de status operacional."""

from django.db import models

from backend.app.modules.printers.machines.django_models import PrinterMachineAdminModel


class PrinterStatusAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    maquina = models.OneToOneField(
        PrinterMachineAdminModel,
        db_column="maquina_id",
        on_delete=models.DO_NOTHING,
        related_name="status_operacional_atual",
    )
    status_operacional = models.CharField("STATUS OPERACIONAL", max_length=20)
    nivel_alerta = models.CharField("NIVEL DE ALERTA", max_length=20)
    mensagem_alerta = models.CharField("MENSAGEM", max_length=255, null=True, blank=True)
    mensagem_operador = models.CharField("ORIENTACAO AO OPERADOR", max_length=255)
    ultima_verificacao_em = models.DateTimeField("ULTIMA VERIFICACAO", null=True, blank=True)
    ultimo_sucesso_em = models.DateTimeField("ULTIMO SUCESSO", null=True, blank=True)
    ultima_falha_em = models.DateTimeField("ULTIMA FALHA", null=True, blank=True)
    tempo_resposta_ms = models.IntegerField("TEMPO DE RESPOSTA (MS)", null=True, blank=True)
    metodo_confirmacao = models.CharField(
        "METODO DE CONFIRMACAO",
        max_length=20,
        null=True,
        blank=True,
    )
    origem = models.CharField("ORIGEM", max_length=40)
    resposta_bruta = models.TextField("RESPOSTA BRUTA", null=True, blank=True)
    criado_em = models.DateTimeField("CRIADO EM", null=True, blank=True)
    atualizado_em = models.DateTimeField("ATUALIZADO EM", null=True, blank=True)

    class Meta:
        app_label = "printer_status"
        managed = False
        db_table = "status_impressoras"
        verbose_name = "Status de impressora"
        verbose_name_plural = "Status de impressoras"

    def __str__(self):
        return f"{self.maquina} - {self.status_operacional}"


class PrinterStatusHistoryAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    maquina = models.ForeignKey(
        PrinterMachineAdminModel,
        db_column="maquina_id",
        on_delete=models.DO_NOTHING,
        related_name="historico_status_confirmado",
    )
    status_anterior = models.CharField("STATUS ANTERIOR", max_length=20)
    status_novo = models.CharField("STATUS NOVO", max_length=20)
    metodo_confirmacao = models.CharField("METODO DE CONFIRMACAO", max_length=20)
    codigo_evento = models.CharField("CODIGO DO EVENTO", max_length=40)
    descricao_evento = models.CharField("DESCRICAO DO EVENTO", max_length=255)
    detalhes = models.JSONField("DETALHES")
    latencia_ms = models.IntegerField("LATENCIA (MS)", null=True, blank=True)
    verificado_em = models.DateTimeField("VERIFICADO EM")
    criado_em = models.DateTimeField("CRIADO EM")

    class Meta:
        app_label = "printer_status"
        managed = False
        db_table = "historico_status_impressoras"
        verbose_name = "Historico de status de impressora"
        verbose_name_plural = "Historico de status de impressoras"

    def __str__(self):
        return f"{self.maquina} - {self.status_anterior} -> {self.status_novo}"


class PrinterLogAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    maquina = models.ForeignKey(
        PrinterMachineAdminModel,
        db_column="maquina_id",
        on_delete=models.DO_NOTHING,
        related_name="logs_operacionais",
    )
    tipo_evento = models.CharField("TIPO DE EVENTO", max_length=40)
    status_anterior = models.CharField("STATUS ANTERIOR", max_length=20, null=True, blank=True)
    status_novo = models.CharField("STATUS NOVO", max_length=20, null=True, blank=True)
    alerta_anterior = models.CharField("ALERTA ANTERIOR", max_length=20, null=True, blank=True)
    alerta_novo = models.CharField("ALERTA NOVO", max_length=20, null=True, blank=True)
    mensagem = models.CharField("MENSAGEM", max_length=255, null=True, blank=True)
    verificado_em = models.DateTimeField("VERIFICADO EM")
    tempo_resposta_ms = models.IntegerField("TEMPO DE RESPOSTA (MS)", null=True, blank=True)
    origem = models.CharField("ORIGEM", max_length=40)
    resposta_bruta = models.TextField("RESPOSTA BRUTA", null=True, blank=True)
    criado_em = models.DateTimeField("CRIADO EM")

    class Meta:
        app_label = "printer_status"
        managed = False
        db_table = "logs_impressoras"
        verbose_name = "Log de impressora"
        verbose_name_plural = "Logs de impressoras"

    def __str__(self):
        return f"{self.maquina} - {self.tipo_evento}"
