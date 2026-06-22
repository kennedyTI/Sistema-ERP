"""Model Django da automacao de novo usuario Windows."""

from django.db import models


class AutomacaoNovoUsuarioWindows(models.Model):
    STATUS_RECEBIDO = "recebido"
    STATUS_IGNORADO = "ignorado"
    STATUS_PROCESSANDO = "processando"
    STATUS_CONCLUIDO = "concluido"
    STATUS_FALHOU = "falhou"
    STATUS_RESPONDIDO = "respondido"
    STATUS_DRY_RUN = "dry_run"

    STATUS_CHOICES = (
        (STATUS_RECEBIDO, "Recebido"),
        (STATUS_IGNORADO, "Ignorado"),
        (STATUS_PROCESSANDO, "Processando"),
        (STATUS_CONCLUIDO, "Concluido"),
        (STATUS_FALHOU, "Falhou"),
        (STATUS_RESPONDIDO, "Respondido"),
        (STATUS_DRY_RUN, "Dry run"),
    )

    id = models.BigAutoField(primary_key=True)

    uidl_email = models.CharField(max_length=255, null=True, blank=True, unique=True)
    message_id_email = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        unique=True,
    )
    remetente = models.CharField(max_length=320, null=True, blank=True)
    destinatario = models.CharField(max_length=320, null=True, blank=True)
    assunto = models.CharField(max_length=500, null=True, blank=True)
    data_email = models.DateTimeField(null=True, blank=True)
    corpo_email = models.TextField(null=True, blank=True)

    pn = models.CharField(max_length=40, null=True, blank=True)
    nome_completo = models.CharField(max_length=255, null=True, blank=True)
    cargo = models.CharField(max_length=255, null=True, blank=True)
    unid_org = models.CharField(max_length=255, null=True, blank=True)
    data_admissao = models.DateField(null=True, blank=True)

    login_gerado = models.CharField(max_length=120, null=True, blank=True)
    login_tentativa_primaria = models.CharField(max_length=120, null=True, blank=True)
    login_tentativa_secundaria = models.CharField(max_length=120, null=True, blank=True)
    login_alternativo_usado = models.BooleanField(default=False)

    dominio_ad = models.CharField(max_length=120, null=True, blank=True)
    ou_destino = models.CharField(max_length=500, null=True, blank=True)
    escritorio = models.CharField(max_length=255, null=True, blank=True)
    empresa = models.CharField(max_length=255, null=True, blank=True)
    grupos_aplicados = models.TextField(null=True, blank=True)

    senha_temporaria_mascarada = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_RECEBIDO,
    )
    dry_run = models.BooleanField(default=True)
    erro = models.TextField(null=True, blank=True)
    resultado_powershell = models.TextField(null=True, blank=True)
    respondido_email = models.BooleanField(default=False)
    email_resposta_enviado_para = models.CharField(
        max_length=320,
        null=True,
        blank=True,
    )

    recebido_em = models.DateTimeField(null=True, blank=True)
    processado_em = models.DateTimeField(null=True, blank=True)
    respondido_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(null=True, blank=True)
    atualizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "automacao_novo_usuario"
        managed = False
        db_table = "automacao_novo_usuario_windows"
        verbose_name = "Automacao de novo usuario Windows"
        verbose_name_plural = "Automacoes de novo usuario Windows"

    def __str__(self):
        return f"{self.nome_completo or self.assunto or self.id} - {self.status}"
