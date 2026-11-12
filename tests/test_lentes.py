import pandas as pd
import pytest

from analise import lentes
from analise.lentes import ackman, buffett, druckenmiller, graham, greenblatt, lynch
from analise.modelo import Dado, Fonte
from analise.valor.dcf import owner_earnings
from tests.conftest import fazer_empresa

_F = Fonte("teste", "2026-01-01")
ANOS = range(2019, 2024)


def serie(*vals):
    return dict(zip(ANOS, vals))


def empresa_boa(**extra):
    M = 1e6
    anual = {
        "lucro_liquido": serie(*(x * M for x in (100, 110, 120, 130, 140))),
        "capital_proprio": serie(*(x * M for x in (600, 650, 700, 750, 800))),
        "receita": serie(*(x * M for x in (1000, 1050, 1100, 1150, 1200))),
        "ebit": serie(*(x * M for x in (150, 157.5, 165, 172.5, 180))),
        "ebitda": serie(*(x * M for x in (200, 207.5, 215, 222.5, 230))),
        "eps": serie(1.0, 1.2, 1.4, 1.7, 2.0),
        "fcf": serie(*(x * M for x in (100, 110, 120, 130, 140))),
        "divida_total": serie(*([200 * M] * 5)),
        "caixa": serie(*([100 * M] * 5)),
        "ativo_corrente": serie(*([500 * M] * 5)),
        "passivo_corrente": serie(*([200 * M] * 5)),
        "imobilizado": serie(*([300 * M] * 5)),
        "amortizacoes": serie(*([20 * M] * 5)),
        "capex": serie(*([-30 * M] * 5)),
    }
    precos = pd.Series([10 + i * 5 / 299 for i in range(300)])
    campos = dict(
        preco=Dado(15.0, _F), acoes=Dado(100 * M, _F), capitalizacao=Dado(1.5e9, _F),
        cambio_eur=Dado(1.5, _F), dividendos={a: 0.3 for a in ANOS}, precos=precos,
        moeda="EUR", beta=Dado(1.0, _F),
    )
    campos.update(extra)
    return fazer_empresa(anual, **campos)


def estados(r):
    return [c.estado for c in r.criterios]


def test_buffett():
    e = empresa_boa()
    r = buffett.avaliar(e)
    assert r.investidor == "Warren Buffett"
    assert estados(r) == ["ok"] * 4
    assert r.criterios[0].valor.startswith("ROE 17")
    assert "≥ 15 %" in r.criterios[0].valor
    assert r.valor_justo == pytest.approx(owner_earnings(e).valor_por_acao * 0.75)


def test_graham():
    r = graham.avaliar(empresa_boa())
    assert r.investidor == "Benjamin Graham"
    assert estados(r) == ["ok"] * 6
    assert r.valor_justo == pytest.approx((22.5 * 2.0 * 8.0) ** 0.5)


def test_lynch():
    r = lynch.avaliar(empresa_boa())
    assert r.investidor == "Peter Lynch"
    assert estados(r) == ["ok"] * 3
    g = ((2.0 / 1.0) ** 0.25 - 1) * 100
    assert r.valor_justo == pytest.approx(2.0 * g)


def test_ackman():
    r = ackman.avaliar(empresa_boa())
    assert r.investidor == "Bill Ackman"
    assert estados(r) == ["ok"] * 4
    assert r.valor_justo == pytest.approx(130e6 / 0.05 / 100e6)


def test_greenblatt():
    r = greenblatt.avaliar(empresa_boa())
    assert r.investidor == "Joel Greenblatt"
    assert estados(r) == ["ok"] * 2
    assert r.valor_justo is None
    ey, roc = 180 / 1600, 180 / 600
    assert r.nota == pytest.approx(((ey - 0.02) / 0.10 * 100 + (roc - 0.05) / 0.35 * 100) / 2)


def test_druckenmiller():
    r = druckenmiller.avaliar(empresa_boa())
    assert r.investidor == "Stanley Druckenmiller"
    assert estados(r) == ["ok"] * 4
    assert r.valor_justo is None
    assert r.resumo == "Sinal favorável"


def test_druckenmiller_desfavoravel():
    precos = pd.Series([15 - i * 5 / 299 for i in range(300)])
    e = empresa_boa(precos=precos)
    assert druckenmiller.avaliar(e).resumo == "Sinal desfavorável"


def test_todas_ordem():
    nomes = [r.investidor for r in lentes.todas(empresa_boa())]
    assert nomes == ["Warren Buffett", "Benjamin Graham", "Peter Lynch",
                     "Bill Ackman", "Joel Greenblatt", "Stanley Druckenmiller"]


def test_criterio_sem_dados_e_nd():
    for r in lentes.todas(fazer_empresa()):
        assert all(c.estado == "nd" and c.valor == "N/D" for c in r.criterios), r.investidor
        assert r.valor_justo is None


def test_falha_quando_nao_cumpre():
    r = graham.avaliar(empresa_boa(preco=Dado(100.0, _F)))
    assert r.criterios[4].estado == "falha"
    assert r.criterios[4].valor.startswith("P/E 50,0")
