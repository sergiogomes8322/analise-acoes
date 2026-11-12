from pytest import approx

from analise.pontuacao import agregar

N = dict(valorizacao=100, qualidade=80, solidez=60, risco_mercado=40, tendencia=20)


def test_pontuacao_pesos():
    assert agregar(N).total == approx(70.0)


def test_pontuacao_redistribui():
    p = agregar({**N, "risco_mercado": None, "tendencia": None})
    assert p.total == approx((0.3 * 100 + 0.25 * 80 + 0.2 * 60) / 0.75)
    assert p.cobertura == approx(0.75)


def test_sem_boa_com_pouca_cobertura():
    p = agregar({"valorizacao": 100})
    assert p.faixa != "Boa" and p.dados_insuficientes and p.cobertura == approx(0.30)


def test_boa_78():
    assert agregar({k: 78 for k in N}).faixa == "Boa"
    assert agregar({k: 77.9 for k in N}).faixa == "Neutra"


def test_sem_dados():
    assert agregar({}).faixa == "Sem dados"


def test_calcular_pontuacao_detalhe():
    from analise.pontuacao import calcular_pontuacao
    from analise.valor.central import ValorCentral
    from tests.conftest import fazer_empresa
    p = calcular_pontuacao(fazer_empresa(), ValorCentral(100, 90, 110, 0.4, 3))
    c = {x.nome: x for x in p.componentes}
    assert c["valorizacao"].nota == 100.0 and c["valorizacao"].detalhe == {"margem_vs_historico": 0.4}
    assert c["solidez"].nota is None and p.cobertura == approx(0.30)


def test_qualidade_usa_roe_em_bancos():
    from analise.pontuacao import calcular_pontuacao
    from analise.valor.central import ValorCentral
    from tests.conftest import fazer_empresa
    anos = range(2021, 2025)
    e = fazer_empresa({"lucro_liquido": {a: 15.0 for a in anos}, "capital_proprio": {a: 100.0 for a in anos},
                       "ebit": {a: 1.0 for a in anos}, "divida_total": {a: 0.0 for a in anos},
                       "caixa": {a: 0.0 for a in anos}}, e_financeira=True)
    q = {x.nome: x for x in calcular_pontuacao(e, ValorCentral(None, None, None, None, 0)).componentes}["qualidade"]
    assert q.detalhe["roe"] == approx(0.15) and "roic" not in q.detalhe
