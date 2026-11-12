import math

import pandas as pd
import pytest
from conftest import fazer_empresa

from analise.indicadores import (
    altman_z, cagr, cobertura_juros, coef_variacao, diluicao_anual,
    divida_liquida_ebitda, fracao_anos_a_crescer, margem_operacional, media,
    momento, piotroski_f, preco_vs_mm200, queda_maxima, roe, roic,
    taxa_imposto, volatilidade_anual,
)
from analise.modelo import Dado, Fonte, Serie

F = Fonte("t", "2026-01-01")


def S(d):
    return Serie(d, F)


def test_cagr():
    assert cagr(S({2022: 100, 2023: 110, 2024: 121}), 5) == pytest.approx((0.10, 2))


def test_cagr_anos_max():
    taxa, n = cagr(S({2020: 1, 2022: 100, 2023: 110, 2024: 121}), 2)
    assert n == 2 and taxa == pytest.approx(0.10)


def test_cagr_negativo_none():
    assert cagr(S({2023: -5, 2024: 10}), 5)[0] is None
    assert cagr(S({2024: 10}), 5)[0] is None


def test_media_cv():
    assert media([1, 2, 3]) == 2
    assert media([]) is None
    assert coef_variacao([1, 3]) == pytest.approx(math.sqrt(2) / 2)
    assert coef_variacao([-1, 1]) is None


def test_fracao_anos():
    assert fracao_anos_a_crescer(S({1: 1, 2: 2, 3: 1, 4: 3})) == pytest.approx(2 / 3)
    assert fracao_anos_a_crescer(S({1: 1})) is None


def test_volatilidade():
    p, v = [100.0], 100.0
    for i in range(260):
        v *= 1.01 if i % 2 == 0 else 1 / 1.01
        p.append(v)
    assert volatilidade_anual(pd.Series(p)) == pytest.approx(0.01 * math.sqrt(252), rel=0.02)
    assert volatilidade_anual(pd.Series([1.0])) is None


def test_queda_maxima():
    assert queda_maxima(pd.Series([100, 120, 60, 90])) == pytest.approx(0.5)
    assert queda_maxima(pd.Series([], dtype=float)) is None


def test_preco_vs_mm200():
    s = pd.Series([100.0] * 199 + [110.0])
    assert preco_vs_mm200(s) == pytest.approx(110 / 100.05 - 1)
    assert preco_vs_mm200(s.iloc[-50:]) is None


def test_momento():
    s = pd.Series(range(1, 300), dtype=float)  # 299 pontos
    # fim = idx 298; meses=12 -> 298-252=46 ; saltar 1 -> 298-21=277
    assert momento(s, 12, 1) == pytest.approx(278 / 47 - 1)
    assert momento(s, 6) == pytest.approx(299 / 173 - 1)
    assert momento(s.iloc[:100], 12, 1) is None


def test_roic_roe_margem_e_impostos():
    e = fazer_empresa(anual={
        "ebit": {2024: 100}, "receita": {2024: 500}, "lucro_liquido": {2024: 60},
        "capital_proprio": {2024: 300}, "divida_total": {2024: 150}, "caixa": {2024: 50},
    })
    assert taxa_imposto(e) == 0.25
    assert roic(e, 2024) == pytest.approx(100 * 0.75 / 400)
    assert roic(e, 2023) is None
    assert roe(e, 2024) == pytest.approx(0.2)
    assert margem_operacional(e, 2024) == pytest.approx(0.2)


def test_roic_capital_nao_positivo():
    e = fazer_empresa(anual={"ebit": {1: 10}, "capital_proprio": {1: 10},
                             "divida_total": {1: 0}, "caixa": {1: 20}})
    assert roic(e, 1) is None


def test_taxa_imposto_media_limitada():
    e = fazer_empresa(anual={
        "impostos": {1: 30, 2: 20, 3: 5}, "resultado_antes_impostos": {1: 100, 2: 100, 3: -50},
    })
    assert taxa_imposto(e) == pytest.approx(0.25)
    e = fazer_empresa(anual={"impostos": {1: 90}, "resultado_antes_impostos": {1: 100}})
    assert taxa_imposto(e) == 0.5


def test_ebitda_negativo():
    e = fazer_empresa(anual={"ebitda": {1: -5}, "divida_total": {1: 10}, "caixa": {1: 1}})
    assert divida_liquida_ebitda(e) is None
    e = fazer_empresa(anual={"ebitda": {1: 50}, "divida_total": {1: 100}, "caixa": {1: 20}})
    assert divida_liquida_ebitda(e) == pytest.approx(1.6)


def test_cobertura_juros():
    e = fazer_empresa(anual={"ebit": {1: 100}, "despesa_juros": {1: 20}})
    assert cobertura_juros(e) == 5
    e = fazer_empresa(anual={"ebit": {1: 100}, "despesa_juros": {1: 0}})
    assert cobertura_juros(e) is None


def test_diluicao():
    e = fazer_empresa(anual={"acoes_media": {1: 100, 2: 103}})
    assert diluicao_anual(e) == pytest.approx(0.03)


def test_altman_z():
    e = fazer_empresa(
        capitalizacao=Dado(600.0, F),
        anual={"ativo_corrente": {1: 300}, "passivo_corrente": {1: 200}, "lucros_retidos": {1: 200},
               "ebit": {1: 100}, "passivo_total": {1: 500}, "ativo_total": {1: 1000},
               "receita": {1: 1200}})
    esperado = 1.2 * 0.1 + 1.4 * 0.2 + 3.3 * 0.1 + 0.6 * 1.2 + 1.0 * 1.2
    assert altman_z(e) == pytest.approx(esperado)
    e.capitalizacao = Dado(None, F)
    assert altman_z(e) is None


def _perfeita():
    return fazer_empresa(anual={
        "lucro_liquido": {1: 10, 2: 30}, "ativo_total": {1: 200, 2: 200},
        "fluxo_operacional": {1: 20, 2: 50}, "divida_longo_prazo": {1: 80, 2: 40},
        "ativo_corrente": {1: 100, 2: 120}, "passivo_corrente": {1: 80, 2: 70},
        "acoes_media": {1: 100, 2: 100}, "lucro_bruto": {1: 40, 2: 60},
        "receita": {1: 100, 2: 120},
    })


def test_piotroski_perfeito():
    assert piotroski_f(_perfeita()) == 9


def test_piotroski_faltas_valem_zero():
    e = _perfeita()
    del e.anual["lucro_bruto"]
    assert piotroski_f(e) == 8


def test_piotroski_sem_ano_anterior():
    e = fazer_empresa(anual={"lucro_liquido": {2: 30}, "ativo_total": {2: 200}})
    assert piotroski_f(e) is None
