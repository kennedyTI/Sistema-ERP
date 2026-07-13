from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.modules.compras.rastreabilidade.importer import (
    ComprasRastreabilidadeImportError,
    importar_rastreabilidade_compras,
)
from backend.app.modules.compras.rastreabilidade.models import (
    ComprasRastreabilidadeExecucao,
    ComprasRastreabilidadeItem,
)
from backend.app.modules.compras.rastreabilidade.schemas import (
    RastreabilidadeContagens,
    RastreabilidadeResultado,
)
from backend.app.modules.integracoes.bdTotvs.exceptions import TotvsQueryError


class FakeService:
    def build_snapshot(self):
        return RastreabilidadeResultado(
            itens=[
                {
                    "filial": "01",
                    "numero_sc": "000001",
                    "item_sc": "0001",
                    "produto": "P001",
                    "descricao_produto": "Produto teste",
                    "quantidade_sc": 5,
                    "data_emissao_sc": "2026-07-01",
                    "data_aprovacao_sc": "2026-07-02",
                    "numero_pedido": "000123",
                    "item_pedido": "0001",
                    "quantidade_recebida_almox": 5,
                    "percentual_recebido": 100,
                    "ultima_data_entrada": "2026-07-05",
                    "compra_efetivada": "Sim - confirmado por entrada no almoxarifado",
                    "situacao_compra": "Comprado e recebido 100% no almoxarifado",
                    "status_estoque_executivo": "Saldo disponivel atende a solicitacao",
                    "payload_completo": {"origem": "unit"},
                }
            ],
            contagens=RastreabilidadeContagens(base_sc_pedido=1, itens_snapshot=1),
        )


class ErrorService:
    def build_snapshot(self):
        raise TotvsQueryError("Falha com segredo PWD=nao_vazar", error_code="TOTVS_QUERY_ERROR")


def make_session():
    engine = create_engine("sqlite:///:memory:")
    ComprasRastreabilidadeExecucao.__table__.create(engine)
    ComprasRastreabilidadeItem.__table__.create(engine)
    return sessionmaker(bind=engine)()


def test_importer_grava_execucao_e_snapshot_sem_json_oficial():
    db = make_session()

    result = importar_rastreabilidade_compras(db, service=FakeService(), criado_por="pytest")

    execution = db.get(ComprasRastreabilidadeExecucao, result.execucao_id)
    items = db.query(ComprasRastreabilidadeItem).all()

    assert result.total_registros == 1
    assert result.contagens.base_sc_pedido == 1
    assert execution.status == "concluida"
    assert execution.criado_por == "pytest"
    assert len(items) == 1
    assert items[0].numero_sc == "000001"
    assert items[0].payload_completo == {"origem": "unit"}


def test_importer_grava_falha_sanitizada_sem_segredos():
    db = make_session()

    try:
        importar_rastreabilidade_compras(db, service=ErrorService())
    except ComprasRastreabilidadeImportError as exc:
        message = str(exc)
    else:
        raise AssertionError("Importador deveria falhar.")

    execution = db.query(ComprasRastreabilidadeExecucao).one()

    assert "TOTVS_QUERY_ERROR" in message
    assert "PWD=" not in message
    assert execution.status == "erro"
    assert execution.total_com_erro == 1
    assert execution.mensagem_erro_sanitizada == message


def test_importer_nao_gera_json_em_arquivo():
    import inspect

    from backend.app.modules.compras.rastreabilidade import importer

    source = inspect.getsource(importer)

    assert "json.dump" not in source
    assert "write_text" not in source
    assert "open(" not in source
