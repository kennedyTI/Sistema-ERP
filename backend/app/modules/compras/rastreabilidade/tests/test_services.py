from backend.app.modules.compras.rastreabilidade.services import build_traceability_items


def test_build_traceability_items_monta_status_executivo_com_entrada_e_local_06():
    items = build_traceability_items(
        base=[
            {
                "C1_FILIAL": "01",
                "C1_NUM": "SC1",
                "C1_ITEM": "0001",
                "C1_PRODUTO": "P001",
                "C1_DESCRI": "Descricao SC",
                "C1_QUANT": 10,
                "C1_EMISSAO": "20260701",
                "C1__DTAPRV": "20260702",
                "C1__NOMAPV": "Aprovador",
                "C1_UNIDREQ": "85050",
                "SC7_C7_NUM": "PC1",
                "SC7_C7_ITEM": "0001",
                "SC7_C7_QUANT": 10,
                "SC7_C7_DATPRF": "20260710",
                "SC7_C7_CONAPRO": "L",
                "SC7_C7_EMITIDO": "",
                "SC7_C7_RESIDUO": "",
            }
        ],
        entradas_agregadas={
            ("01", "PC1", "0001"): {
                "quantidade_recebida": 10,
                "ultimo_local_entrada": "06",
                "primeira_data_entrada": "20260708",
                "ultima_data_entrada": "20260708",
                "ultima_serie": "1",
            }
        },
        fiscal_financeiro={
            ("01", "PC1", "0001"): {
                "nf_lancada_fiscal": "Sim",
                "ultimo_documento_fiscal": "NF1",
                "virou_titulo_financeiro": "Sim",
                "status_pagamento_financeiro": "Pago",
            }
        },
        produtos={"P001": {"B1_COD": "P001", "B1_DESC": "Produto P001", "B1_LOCPAD": "01"}},
        estoques={("01", "P001", "06"): {"B2_QATU": 0, "B2_RESERVA": 0, "B2_QEMP": 0}},
        locais_por_codigo={"06": [{"NNR_FILIAL": "01", "NNR_CODIGO": "06", "NNR_DESCRI": "Consumo"}]},
    )

    assert len(items) == 1
    assert items[0]["descricao_produto"] == "Produto P001"
    assert items[0]["sc_aprovada"] == "Sim"
    assert items[0]["compra_efetivada"] == "Sim - confirmado por entrada no almoxarifado"
    assert items[0]["status_prazo_entrega"] == "Recebido 100% no prazo"
    assert items[0]["status_estoque_executivo"] == "Entrada em consumo direto"
    assert items[0]["nome_local_estoque_consultado"] == "Consumo"
