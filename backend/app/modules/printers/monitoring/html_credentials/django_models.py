"""Espelho Django unmanaged das credenciais de coleta HTML."""

from django.db import models

from backend.app.modules.printers.machines.django_models import PrinterModelAdminModel


class PrinterCollectionCredentialAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    descricao = models.TextField("DESCRICAO", null=True, blank=True)
    tipo_autenticacao = models.CharField(
        "TIPO AUTENTICACAO",
        max_length=20,
        choices=(
            ("basic", "basic"),
            ("digest", "digest"),
            ("form", "form"),
            ("cookie", "cookie"),
        ),
    )
    modelo = models.ForeignKey(
        PrinterModelAdminModel,
        verbose_name="MODELO",
        db_column="modelo_id",
        on_delete=models.DO_NOTHING,
        related_name="credenciais_coleta",
    )
    usuario = models.CharField("USUARIO", max_length=160, null=True, blank=True)
    senha_criptografada = models.TextField("SENHA CRIPTOGRAFADA")
    caminho_status = models.CharField("CAMINHO STATUS", max_length=500, null=True, blank=True)
    caminho_informacoes = models.CharField(
        "CAMINHO INFORMACOES",
        max_length=500,
        null=True,
        blank=True,
    )
    caminho_login = models.CharField("CAMINHO LOGIN", max_length=500, null=True, blank=True)
    timeout_segundos = models.IntegerField("TIMEOUT SEGUNDOS", default=5)
    protocolo_preferencial = models.CharField(
        "PROTOCOLO PREFERENCIAL",
        max_length=10,
        choices=(("auto", "auto"), ("http", "http"), ("https", "https")),
        default="auto",
    )
    validar_ssl = models.BooleanField("VALIDAR SSL", default=False)
    ativo = models.BooleanField("ATIVO", default=True)
    criado_em = models.DateTimeField("CRIADO EM", null=True, blank=True)
    atualizado_em = models.DateTimeField("ATUALIZADO EM", null=True, blank=True)

    class Meta:
        app_label = "printer_machines"
        managed = False
        db_table = "credenciais_coleta_impressoras"
        verbose_name = "credencial_coleta_impressora"
        verbose_name_plural = "credenciais_coleta_impressoras"

    def __str__(self):
        return str(self.modelo)
