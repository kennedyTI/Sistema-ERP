"""Modelo virtual usado apenas para registrar permissoes no Django Auth."""

from django.db import models


class PermissoesImpressoras(models.Model):
    class Meta:
        app_label = "impressoras"
        managed = False
        db_table = "permissoes_impressoras"
        default_permissions = ()
        permissions = (
            ("ver_dashboard", "Pode visualizar o dashboard de impressoras"),
            ("ver_status", "Pode visualizar o status operacional de impressoras"),
            ("ver_maquinas", "Pode visualizar as maquinas cadastradas"),
            ("criar_maquinas", "Pode criar maquinas"),
            ("editar_maquinas", "Pode editar maquinas"),
            ("alternar_status_maquinas", "Pode ativar ou inativar maquinas"),
            ("ver_papel", "Pode visualizar o modulo de papel"),
        )
        verbose_name = "Permissao de impressoras"
        verbose_name_plural = "Permissoes de impressoras"
