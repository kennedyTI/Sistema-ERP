import inspect

import pytest

from backend.app.modules.compras.rastreabilidade import repository
from backend.app.modules.integracoes.bdTotvs.exceptions import TotvsQueryError


def test_repository_usa_bdTotvs_para_base(monkeypatch):
    calls = []

    def fake_execute_query(sql, params=None):
        calls.append((sql, params))
        return [{"C1_NUM": "000001"}]

    monkeypatch.setattr(repository.bdTotvs, "execute_query", fake_execute_query)

    result = repository.ComprasRastreabilidadeRepository().fetch_base_sc_pedido()

    assert result == [{"C1_NUM": "000001"}]
    assert "vwSC1010" in calls[0][0]
    assert calls[0][1] is None


def test_repository_expande_values_parametrizado(monkeypatch):
    calls = []

    def fake_execute_query(sql, params=None):
        calls.append((sql, params))
        return [{"D1_DOC": "NF1"}]

    monkeypatch.setattr(repository.bdTotvs, "execute_query", fake_execute_query)

    result = repository.ComprasRastreabilidadeRepository().fetch_entradas_sd1(
        [("01", "000123", "0001"), ("01", "000124", "0002")]
    )

    assert result == [{"D1_DOC": "NF1"}]
    assert "VALUES (?, ?, ?)," in calls[0][0]
    assert calls[0][1] == ("01", "000123", "0001", "01", "000124", "0002")


def test_repository_nao_consulta_quando_nao_ha_chaves(monkeypatch):
    def fail_execute_query(sql, params=None):
        raise AssertionError("Nao deveria consultar bdTotvs sem chaves.")

    monkeypatch.setattr(repository.bdTotvs, "execute_query", fail_execute_query)

    assert repository.ComprasRastreabilidadeRepository().fetch_fiscal_sf1([]) == []


def test_repository_propaga_erro_sanitizado_do_bdtotvs(monkeypatch):
    def fake_execute_query(sql, params=None):
        raise TotvsQueryError("Falha sanitizada.", error_code="TOTVS_QUERY_ERROR")

    monkeypatch.setattr(repository.bdTotvs, "execute_query", fake_execute_query)

    with pytest.raises(TotvsQueryError) as exc_info:
        repository.ComprasRastreabilidadeRepository().fetch_produtos_sb1([("P001",)])

    assert exc_info.value.error_code == "TOTVS_QUERY_ERROR"
    assert "PWD=" not in str(exc_info.value)


def test_repository_nao_importa_pyodbc_diretamente():
    source = inspect.getsource(repository)

    assert "import pyodbc" not in source
    assert "connect(" not in source
