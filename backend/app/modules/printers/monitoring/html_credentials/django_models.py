"""Espelho Django unmanaged das credenciais de coleta HTML."""

from django.db import models

from backend.app.modules.printers.machines.django_models import PrinterModelAdminModel


class PrinterCollectionCredentialAdminModel(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField("NOME", max_length=160)
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
    usuario = models.CharField("USUARIO", max_length=160)
    senha_criptografada = models.TextField("SENHA CRIPTOGRAFADA")
    ativo = models.BooleanField("ATIVO", default=True)
    criado_em = models.DateTimeField("CRIADO EM", null=True, blank=True)
    atualizado_em = models.DateTimeField("ATUALIZADO EM", null=True, blank=True)

    class Meta:
        app_label = "printer_machines"
        managed = False
        db_table = "credenciais_coleta_impressoras"
        verbose_name = "Credencial de coleta de impressora"
        verbose_name_plural = "CREDENCIAIS_COLETA_IMPRESSORAS"

    def __str__(self):
        return f"{self.nome} - {self.modelo}"

