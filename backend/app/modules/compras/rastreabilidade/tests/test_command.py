from io import StringIO

from django.core.management.base import CommandError

from backend.app.modules.backoffice.management.commands import (
    importar_rastreabilidade_compras as command_module,
)
from backend.app.modules.compras.rastreabilidade.importer import (
    ComprasRastreabilidadeImportError,
    ImportacaoRastreabilidadeResultado,
)
from backend.app.modules.compras.rastreabilidade.models import ComprasRastreabilidadeExecucao
from backend.app.modules.compras.rastreabilidade.schemas import RastreabilidadeContagens
from backend.app.modules.compras.rastreabilidade.workflow import (
    RastreabilidadeImportacaoEmAndamento,
)


class FakeSession:
    closed = False

    def close(self):
        self.closed = True


def test_command_imprime_saida_sanitizada(monkeypatch):
    fake_session = FakeSession()

    def fake_import(db, **kwargs):
        assert db is fake_session
        assert kwargs["origem"] == "comando"
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
    monkeypatch.setattr(command_module, "get_redis_client", lambda: object())
    monkeypatch.setattr(command_module, "executar_importacao_com_lock", fake_import)

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

    def fake_import(db, **kwargs):
        raise ComprasRastreabilidadeImportError("Falha bdTotvs sanitizada: TOTVS_QUERY_ERROR.")

    monkeypatch.setattr(command_module, "get_redis_client", lambda: object())
    monkeypatch.setattr(command_module, "executar_importacao_com_lock", fake_import)

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


def test_command_informa_importacao_em_andamento(monkeypatch):
    fake_session = FakeSession()
    execution = ComprasRastreabilidadeExecucao(id=77, status="em_andamento", origem="manual")

    def fake_import(db, **kwargs):
        raise RastreabilidadeImportacaoEmAndamento(execution)

    monkeypatch.setattr(command_module, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(command_module, "get_redis_client", lambda: object())
    monkeypatch.setattr(command_module, "executar_importacao_com_lock", fake_import)

    command = command_module.Command(stdout=StringIO())
    command.handle()
    output = command.stdout.getvalue()

    assert fake_session.closed is True
    assert "Ja existe importacao em andamento" in output
    assert "77" in output


def test_command_erro_de_orquestracao_nao_expoe_stacktrace(monkeypatch):
    fake_session = FakeSession()

    def fake_import(db, **kwargs):
        raise RuntimeError("redis://host-interno:6379 segredo tecnico")

    monkeypatch.setattr(command_module, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(command_module, "get_redis_client", lambda: object())
    monkeypatch.setattr(command_module, "executar_importacao_com_lock", fake_import)

    command = command_module.Command(stdout=StringIO())

    try:
        command.handle()
    except CommandError as exc:
        message = str(exc)
    else:
        raise AssertionError("Comando deveria falhar.")

    output = command.stdout.getvalue()
    assert "falha sanitizada na orquestracao" in output
    assert "redis://host-interno" not in output
    assert "Falha ao importar rastreabilidade de compras" in message
