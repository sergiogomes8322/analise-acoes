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


def _emp(**anual):
    return fazer_empresa({k: {2025: v} for k, v in anual.items()}, moeda="EUR")


def test_fcf_negativo_conta():
    a = alertas(_emp(fcf=-5.0))
    assert [x.nome for x in a] == ["FCF negativo"]
    assert etiqueta_risco(a + _a(1)) == "Médio"


def test_cobertura_juros_informativa():
    a = alertas(_emp(ebit=100.0, despesa_juros=50.0))
    assert [x.nome for x in a] == ["Cobertura de juros"]
    assert etiqueta_risco(a) == "Baixo"
    assert etiqueta_risco(_a(2) + a) == "Médio"


def test_informativos_nao_contam():
    info = [CAMBIO, Alerta("Cobertura de juros", "1,00", "< 3,00")]
    assert etiqueta_risco(_a(4) + info) == "Alto"
    assert etiqueta_risco(_a(1) + info) == "Baixo"


def test_lucros_concentrados_informativo():
    e = fazer_empresa({"lucro_liquido": {2019: 999.0, 2020: 10.0, 2021: -5.0, 2022: 10.0, 2023: 10.0,
                                         2024: 100.0}}, moeda="EUR")
    a = alertas(e)  # 2019 fora da janela de 5 anos; 100 / 130 > 50 %
    assert [(x.nome, x.valor, x.limite) for x in a] == [("Lucros concentrados num ano", "76,9 %", "> 50,0 %")]
    assert etiqueta_risco(a + _a(1)) == "Baixo"


def test_lucros_repartidos_sem_alerta():
    e = fazer_empresa({"lucro_liquido": {a: 10.0 for a in range(2020, 2025)}}, moeda="EUR")
    assert alertas(e) == []
