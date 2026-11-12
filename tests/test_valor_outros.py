import pandas as pd
import pytest

from analise.modelo import Dado, Fonte, ResultadoMetodo
from analise.valor.central import valor_central
from analise.valor.outros import (epv, ev_ebit_historico, formula_graham, gordon,
                                  numero_graham, pb_bancos, pe_historico, todos_os_metodos)
from tests.conftest import fazer_empresa

F = Fonte("t", "2026-01-01")


def D(x):
    return Dado(x, F)


def test_formula_graham():
    e = fazer_empresa(anual={"eps": {2023: 5 / 1.1, 2024: 5.0}}, taxa_sem_risco=D(0.034))
    r = formula_graham(e)
    assert r.aplicavel and r.valor_por_acao == pytest.approx(142.5)


def test_formula_graham_eps_negativo():
    r = formula_graham(fazer_empresa(anual={"eps": {2024: -1.0}}, taxa_sem_risco=D(0.034)))
    assert not r.aplicavel and r.valor_por_acao is None and r.motivo


def test_numero_graham():
    e = fazer_empresa(anual={"eps": {2024: 4.0}, "capital_proprio": {2024: 250.0}}, acoes=D(10))
    assert numero_graham(e).valor_por_acao == pytest.approx(47.434, abs=1e-3)


def test_numero_graham_eps_negativo():
    e = fazer_empresa(anual={"eps": {2024: -4.0}, "capital_proprio": {2024: 250.0}}, acoes=D(10))
    r = numero_graham(e)
    assert not r.aplicavel and r.valor_por_acao is None


def test_epv():
    anos = range(2020, 2025)
    e = fazer_empresa(
        anual={"ebit": {a: 100.0 for a in anos},
               "resultado_antes_impostos": {a: 100.0 for a in anos},
               "impostos": {a: 25.0 for a in anos},
               "caixa": {2024: 100.0}, "divida_total": {2024: 200.0}},
        acoes=D(10), taxa_sem_risco=D(0.025), beta=D(1.0))
    # r = max(0.025 + 0.055, 0.08) = 0.08
    assert epv(e).valor_por_acao == pytest.approx(83.75)


def test_epv_financeira():
    assert not epv(fazer_empresa(e_financeira=True)).aplicavel


def test_gordon_corte():
    e = fazer_empresa(dividendos={2022: 1.0, 2023: 1.0, 2024: 0.5}, acoes=D(10))
    r = gordon(e)
    assert not r.aplicavel and r.valor_por_acao is None


def test_gordon_ok():
    e = fazer_empresa(dividendos={2022: 1.0, 2023: 1.0, 2024: 1.0}, acoes=D(10),
                      taxa_sem_risco=D(0.025), beta=D(1.0))
    r = gordon(e)  # g = 0 -> 1 / 0.08
    assert r.valor_por_acao == pytest.approx(12.5)


def _precos():
    idx = pd.to_datetime([f"{a}-12-30" for a in range(2020, 2025)])
    return pd.Series([10.0, 20.0, 30.0, 40.0, 50.0], index=idx)


def test_pe_historico():
    eps = {a: 2.0 for a in range(2020, 2025)}  # P/E 5,10,15,20,25 -> mediana 15
    r = pe_historico(fazer_empresa(anual={"eps": eps}, precos=_precos()))
    assert r.valor_por_acao == pytest.approx(30.0)


def test_pe_historico_poucos_anos():
    r = pe_historico(fazer_empresa(anual={"eps": {2023: 2.0, 2024: 2.0}}, precos=_precos()))
    assert not r.aplicavel


def test_ev_ebit_historico():
    anos = range(2020, 2025)
    e = fazer_empresa(
        anual={"ebit": {a: 10.0 for a in anos}, "divida_total": {a: 0.0 for a in anos},
               "caixa": {a: 0.0 for a in anos}, "acoes_media": {a: 1.0 for a in anos}},
        acoes=D(1), precos=_precos())
    # EV/EBIT 1..5 -> mediana 3 -> EV 30 / 1 acao
    assert ev_ebit_historico(e).valor_por_acao == pytest.approx(30.0)


def test_pb_bancos():
    anos = range(2020, 2025)
    e = fazer_empresa(e_financeira=True, acoes=D(10),
                      anual={"lucro_liquido": {a: 8.0 for a in anos},
                             "capital_proprio": {a: 100.0 for a in anos}},
                      taxa_sem_risco=D(0.025), beta=D(1.0))
    assert pb_bancos(e).valor_por_acao == pytest.approx(10.0)  # 0.08/0.08 * 10
    assert not pb_bancos(fazer_empresa()).aplicavel


def test_todos_ordem():
    nomes = [m.nome for m in todos_os_metodos(fazer_empresa())]
    assert len(nomes) == 9 and nomes[:2] == ["DCF", "Owner earnings"]


def _m(v):
    return ResultadoMetodo("x", v, v is not None)


def test_valor_central():
    c = valor_central([_m(80.0), _m(100.0), _m(130.0), _m(None)], 85.0)
    assert (c.central, c.minimo, c.maximo, c.n_metodos) == (100.0, 80.0, 130.0, 3)
    assert c.margem == pytest.approx(0.15)


def test_valor_central_vazio():
    c = valor_central([_m(None)], 85.0)
    assert c.central is None and c.margem is None and c.n_metodos == 0
