import datetime as dt

from backend.app.modules.compras.rastreabilidade.rules import (
    compra_efetivada,
    situacao_compra,
    status_estoque_executivo,
    status_pedido_liberacao,
    status_prazo_entrega,
    status_recebimento,
)


def test_compra_efetivada_confirmada_por_entrada_mesmo_sem_emitido():
    assert (
        compra_efetivada("000123", "L", "", 1)
        == "Sim - confirmado por entrada no almoxarifado"
    )


def test_situacao_compra_liberada_emitida_aguardando_almoxarifado():
    assert (
        situacao_compra("000123", "L", "S", "", 0, 10)
        == "Comprado - aguardando entrada no almoxarifado"
    )


def test_status_prazo_entrega_recebido_total_no_prazo():
    assert (
        status_prazo_entrega(
            "000123",
            dt.date(2026, 7, 20),
            dt.date(2026, 7, 18),
            dt.date(2026, 7, 19),
            10,
            10,
            "L",
            "S",
        )
        == "Recebido 100% no prazo"
    )


def test_status_prazo_entrega_pedido_liberado_nao_emitido_sem_entrada():
    assert (
        status_prazo_entrega(
            "000123",
            dt.date(2026, 7, 20),
            None,
            None,
            0,
            10,
            "L",
            "",
            today=dt.date(2026, 7, 13),
        )
        == "Nao avaliado - pedido nao emitido"
    )


def test_status_estoque_executivo_local_06_consumo_direto():
    assert (
        status_estoque_executivo(
            local="06",
            quantidade_recebida=2,
            saldo_disponivel=0,
            quantidade_solicitada=10,
        )
        == "Entrada em consumo direto"
    )


def test_status_estoque_executivo_saldo_total_parcial_e_sem_saldo():
    assert (
        status_estoque_executivo(
            local="01",
            quantidade_recebida=0,
            saldo_disponivel=10,
            quantidade_solicitada=10,
        )
        == "Saldo disponivel atende a solicitacao"
    )
    assert (
        status_estoque_executivo(
            local="01",
            quantidade_recebida=0,
            saldo_disponivel=4,
            quantidade_solicitada=10,
        )
        == "Saldo disponivel atende parcialmente"
    )
    assert (
        status_estoque_executivo(
            local="01",
            quantidade_recebida=0,
            saldo_disponivel=0,
            quantidade_solicitada=10,
        )
        == "Sem saldo disponivel"
    )


def test_status_recebimento_total_parcial_sem_pedido_e_sem_entrada():
    assert status_recebimento("000123", 10, 10) == "Recebido 100%"
    assert status_recebimento("000123", 4, 10) == "Recebido parcialmente"
    assert status_recebimento("", 0, 10) == "Sem pedido"
    assert status_recebimento("000123", 0, 10) == "Sem entrada no almoxarifado"


def test_status_pedido_liberacao_sem_pedido_e_bloqueado():
    assert status_pedido_liberacao("", "L") == "Sem pedido"
    assert status_pedido_liberacao("000123", "B") == "Bloqueado"
