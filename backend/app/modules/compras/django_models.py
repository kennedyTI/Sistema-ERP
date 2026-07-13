"""Modelo virtual usado apenas para registrar permissoes de Compras."""

from django.db import models


class PermissoesCompras(models.Model):
    class Meta:
        app_label = "compras"
        managed = False
        db_table = "permissoes_compras"
        default_permissions = ()
        permissions = (
            ("ver_rastreabilidade", "Pode visualizar rastreabilidade de compras"),
            ("atualizar_rastreabilidade", "Pode atualizar rastreabilidade de compras"),
        )
        verbose_name = "Permissao de compras"
        verbose_name_plural = "Permissoes de compras"
