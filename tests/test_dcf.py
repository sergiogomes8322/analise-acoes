import pytest

from analise.modelo import Dado, Fonte, Serie
from analise.valor.dcf import dcf, owner_earnings, taxa_desconto, valor_presente
from tests.conftest import fazer_empresa

_F = Fonte("teste", "2026-01-01")


def _dado(x):
    return Dado(x, _F)


def _empresa(fcf=(100, 100, 100), **campos):
    anos = {2022 + i: v for i, v in enumerate(fcf)}
    receita = {2022 + i: 1000 * 1.025 ** i for i in range(3)}
    return fazer_empresa(
        anual={"fcf": anos, "receita": receita},
        acoes=_dado(10), taxa_sem_risco=_dado(0.025), beta=_dado(1.0), **campos)


def test_vp_igual_gordon_quando_g_constante():
    assert valor_presente(100, 0.025, 0.025, 0.08, 10) == pytest.approx(1863.636, rel=1e-4)


def test_dcf_por_acao():
    r = dcf(_empresa())
    assert r.aplicavel and r.valor_por_acao == pytest.approx(186.36, rel=1e-3)
    assert set(r.pressupostos) == {"g0", "gT", "r", "base", "anos_historico", "histórico"}


def test_dcf_fcf_negativo():
    r = dcf(_empresa(fcf=(-100, -100, -100)))
    assert not r.aplicavel and r.valor_por_acao is None and r.motivo == "FCF médio negativo"


def test_dcf_banco():
    r = dcf(_empresa(e_financeira=True))
    assert not r.aplicavel and r.motivo == "Não aplicável a bancos/seguradoras"


def test_dcf_sem_acoes():
    e = _empresa()
    e.acoes = _dado(None)
    assert dcf(e).motivo == "Sem número de ações"


def test_taxa_desconto_minima():
    e = fazer_empresa(taxa_sem_risco=_dado(0.01), beta=_dado(0.5))
    assert taxa_desconto(e) == pytest.approx(0.08)


def test_owner_earnings():
    e = fazer_empresa(
        anual={"lucro_liquido": {2022: 90, 2023: 95, 2024: 100}, "amortizacoes": {2024: 20},
               "capex": {2022: -30, 2023: -30, 2024: -30}},
        acoes=_dado(10), taxa_sem_risco=_dado(0.025), beta=_dado(1.0))
    r = owner_earnings(e)
    assert r.aplicavel and r.pressupostos["base"] == pytest.approx(90)


def test_owner_earnings_negativos():
    e = fazer_empresa(
        anual={"lucro_liquido": {2022: 10, 2023: 10, 2024: 10}, "amortizacoes": {2024: 0},
               "capex": {2022: -50, 2023: -50, 2024: -50}},
        acoes=_dado(10))
    r = owner_earnings(e)
    assert not r.aplicavel and r.valor_por_acao is None and r.motivo == "Owner earnings negativos"


def test_dcf_historico_insuficiente():
    r = dcf(_empresa(fcf=(100, 100)))
    assert not r.aplicavel and r.motivo == "Histórico insuficiente (2 anos)"


def test_g0_usa_so_os_ultimos_5_anos():
    e = _empresa()
    e.anual["receita"] = Serie({**{2010 + i: 10.0 * 2 ** i for i in range(5)},
                                **{2020 + i: 1000.0 for i in range(5)}}, _F)
    assert dcf(e).pressupostos["g0"] == 0.0


def test_dcf_indica_anos_usados_no_crescimento():
    r = dcf(_empresa())  # receita só com 3 anos
    assert r.pressupostos["histórico"] == "CAGR de 3 anos (pedidos 5)"
