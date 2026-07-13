from io import StringIO

from django.core.management.base import CommandError

from backend.app.modules.backoffice.management.commands import (
    importar_rastreabilidade_compras as command_module,
)
from backend.app.modules.compras.rastreabilidade.importer import (
    ComprasRastreabilidadeImportError,
    ImportacaoRastreabilidadeResultado,
)
from backend.app.modules.compras.rastreabilidade.schemas import RastreabilidadeContagens


class FakeSession:
    closed = False

    def close(self):
        self.closed = True


def test_command_imprime_saida_sanitizada(monkeypatch):
    fake_session = FakeSession()

    def fake_import(db):
        assert db is fake_session
        return ImportacaoRastreabilidadeResultado(
            execucao_id=1,
            total_registros=2,
            contagens=RastreabilidadeContagens(
                base_sc_pedido=2,
                entradas_sd1=2,
                fiscal_sf1=1,
                financeiro_se2=1,
                produtos_sb1=2,
                estoque_sb2=2,
                locais_nnr=1,
                itens_snapshot=2,
            ),
        )

    monkeypatch.setattr(command_module, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(command_module, "importar_rastreabilidade_compras", fake_import)

    command = command_module.Command(stdout=StringIO())
    command.handle()
    output = command.stdout.getvalue()

    assert fake_session.closed is True
    assert "Snapshot gravado: 2 itens" in output
    assert "PWD=" not in output
    assert "SERVER=" not in output


def test_command_erro_mantem_mensagem_publica_sanitizada(monkeypatch):
    fake_session = FakeSession()

    monkeypatch.setattr(command_module, "SessionLocal", lambda: fake_session)

    def fake_import(db):
        raise ComprasRastreabilidadeImportError("Falha bdTotvs sanitizada: TOTVS_QUERY_ERROR.")

    monkeypatch.setattr(command_module, "importar_rastreabilidade_compras", fake_import)

    command = command_module.Command(stdout=StringIO())

    try:
        command.handle()
    except CommandError as exc:
        message = str(exc)
    else:
        raise AssertionError("Comando deveria falhar.")

    output = command.stdout.getvalue()
    assert fake_session.closed is True
    assert "TOTVS_QUERY_ERROR" in output
    assert "PWD=" not in output
    assert "Falha ao importar rastreabilidade de compras" in message
