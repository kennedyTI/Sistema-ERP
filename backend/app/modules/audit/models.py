"""
Models Django expostos no Admin da base v2 limpa.

O Django continua sem ownership das tabelas operacionais. Alembic cria as
tabelas genericas de logs/auditoria no schema operacional.
"""

from django.db import models


class Log(models.Model):
    id = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=255, null=True, blank=True)
    message = models.CharField(max_length=255, null=True, blank=True)
    valor_anterior = models.CharField(max_length=255, null=True, blank=True)
    valor_novo = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "logs"
        verbose_name = "Log"
        verbose_name_plural = "Logs"

    def __str__(self):
        return self.message or f"Log #{self.id}"


class AuditLog(models.Model):
    id = models.AutoField(primary_key=True)
    table_name = models.CharField(max_length=255)
    record_id = models.IntegerField(null=True, blank=True)
    action = models.CharField(max_length=255)
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)
    changed_by = models.CharField(max_length=255, null=True, blank=True)
    source = models.CharField(max_length=255)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "audit_logs"
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        return f"{self.table_name}#{self.record_id} - {self.action}"
