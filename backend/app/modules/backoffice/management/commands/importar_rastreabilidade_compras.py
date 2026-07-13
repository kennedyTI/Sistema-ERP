"""Comando sanitizado para importar rastreabilidade de compras."""

from django.core.management.base import BaseCommand, CommandError

from backend.app.core.database import SessionLocal
from backend.app.modules.compras.rastreabilidade.importer import (
    ComprasRastreabilidadeImportError,
    importar_rastreabilidade_compras,
)


class Command(BaseCommand):
    help = "Importa snapshot de rastreabilidade de compras via bdTotvs"

    def handle(self, *args, **options):
        self.stdout.write("[Compras] Iniciando importacao da rastreabilidade.")
        db = SessionLocal()
        try:
            result = importar_rastreabilidade_compras(db)
        except ComprasRastreabilidadeImportError as exc:
            self.stdout.write(f"[Compras] Importacao falhou: {exc}")
            raise CommandError("Falha ao importar rastreabilidade de compras.") from exc
        finally:
            db.close()

        counts = result.contagens
        self.stdout.write(f"[Compras] Base SC + Pedido: {counts.base_sc_pedido} registros.")
        self.stdout.write(f"[Compras] Entradas SD1: {counts.entradas_sd1} registros.")
        self.stdout.write(f"[Compras] Fiscal SF1: {counts.fiscal_sf1} registros.")
        self.stdout.write(f"[Compras] Financeiro SE2: {counts.financeiro_se2} registros.")
        self.stdout.write(f"[Compras] Produtos SB1: {counts.produtos_sb1} registros.")
        self.stdout.write(f"[Compras] Estoque SB2: {counts.estoque_sb2} registros.")
        self.stdout.write(f"[Compras] Locais NNR: {counts.locais_nnr} registros.")
        self.stdout.write(f"[Compras] Snapshot gravado: {result.total_registros} itens.")
        self.stdout.write("[Compras] Importacao concluida.")
