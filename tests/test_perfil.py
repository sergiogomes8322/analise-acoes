from analise.perfil import Alerta, alertas, classificar, etiqueta_risco
from tests.conftest import fazer_empresa

CAMBIO = Alerta("Moeda ≠ EUR (risco cambial)", "USD", "EUR")


def _a(n):
    return [Alerta(f"a{i}", "x", "y") for i in range(n)]


def test_etiqueta_risco():
    assert etiqueta_risco(_a(0)) == "Baixo" and etiqueta_risco(_a(1)) == "Baixo"
    assert etiqueta_risco(_a(2)) == "Médio" and etiqueta_risco(_a(3)) == "Médio"
    assert etiqueta_risco(_a(4)) == "Alto"
    assert etiqueta_risco(_a(1) + [CAMBIO]) == "Baixo"


def test_classificar_crescimento():
    e = fazer_empresa({"receita": {2022: 100, 2023: 120, 2024: 144, 2025: 172.8}})
    perfil, razoes = classificar(e, 10.0)
    assert perfil == "Crescimento" and "20,0 %" in razoes[0]


def test_classificar_valor():
    e = fazer_empresa({"eps": {2025: 1.0}})
    assert classificar(e, 10.0)[0] == "Valor"


def test_classificar_misto():
    e = fazer_empresa({"eps": {2025: 1.0}})
    assert classificar(e, 20.0)[0] == "Misto"


def test_alertas_moeda():
    e = fazer_empresa(moeda="USD")
    a = alertas(e)
    assert [x.nome for x in a] == ["Moeda ≠ EUR (risco cambial)"]
    assert etiqueta_risco(a) == "Baixo"


def test_alertas_beta():
    from analise.modelo import Dado, Fonte
    e = fazer_empresa(moeda="EUR", beta=Dado(1.8, Fonte("t", "d")))
    a = alertas(e)
    assert len(a) == 1 and a[0].nome == "Beta" and a[0].valor == "1,80"
