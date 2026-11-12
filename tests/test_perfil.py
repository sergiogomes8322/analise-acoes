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


# --- Perfil da empresa (etiquetas) ---
from analise.modelo import Dado, Fonte  # noqa: E402
from analise.perfil import etiquetas  # noqa: E402

_F = Fonte("teste", "2026-01-01")
ANOS = range(2021, 2026)


def _d(v):
    return Dado(v, _F)


def _nomes(e, preco):
    return {t.nome for t in etiquetas(e, preco)}


def test_blue_chip_grande_defensiva_rendimento():
    e = fazer_empresa({"lucro_liquido": {a: 10.0 for a in ANOS}, "receita": {a: 100 * 1.08 ** i for i, a in enumerate(ANOS)},
                       "ebitda": {2025: 50.0}, "divida_total": {2025: 60.0}, "caixa": {2025: 20.0}},
                      capitalizacao=_d(50e9), cambio_eur=_d(1.0), setor="Consumer Defensive",
                      dividendos={a: 2.0 for a in ANOS})
    n = _nomes(e, 50.0)
    assert {"Blue chip", "Grande empresa", "Defensiva", "Crescimento estável", "Rendimento (dividendos)"} <= n


def test_penny_small_cap_especulativa():
    e = fazer_empresa({"lucro_liquido": {2024: -5.0, 2025: -3.0}}, capitalizacao=_d(300e6), cambio_eur=_d(1.0))
    n = _nomes(e, 2.0)
    assert {"Penny stock", "Pequena empresa", "Small cap especulativa", "Não paga dividendo"} <= n
    assert "Blue chip" not in n


def test_lynch_recuperacao_ativos_ciclica_rapido_lento():
    rec = fazer_empresa({"lucro_liquido": {2024: -5.0, 2025: 3.0}})
    assert "Recuperação" in _nomes(rec, 10.0)
    ativos = fazer_empresa({"capital_proprio": {2025: 2000.0}}, acoes=_d(100.0))
    assert "Rica em ativos" in _nomes(ativos, 10.0)  # P/B 0,5
    cic = fazer_empresa({"receita": {a: 100.0 for a in ANOS}}, setor="Energy")
    assert {"Cíclica (Lynch)", "Cíclica"} <= _nomes(cic, 10.0)
    rapido = fazer_empresa({"receita": {a: 100 * 1.2 ** i for i, a in enumerate(ANOS)}})
    assert "Crescimento rápido" in _nomes(rapido, 10.0)
    lento = fazer_empresa({"receita": {a: 100 * 1.02 ** i for i, a in enumerate(ANOS)}})
    assert "Crescimento lento" in _nomes(lento, 10.0)


def test_sensivel_ao_juro_e_media():
    e = fazer_empresa(setor="Financial Services", capitalizacao=_d(5e9), cambio_eur=_d(1.0))
    assert {"Sensível ao juro", "Média empresa"} <= _nomes(e, 10.0)


def test_etiquetas_explicam_e_nao_rebentam_sem_dados():
    ts = etiquetas(fazer_empresa(), 10.0)
    assert [t.grupo for t in ts][0] == "Estilo"  # estilo aparece sempre
    assert all(t.explicacao for t in ts)
