import pytest
from streamlit.testing.v1 import AppTest

from analise import servico
from analise.fontes import yahoo
from analise.modelo import (Componente, Criterio, Dado, Empresa, Fonte, Pontuacao, ResultadoLente,
                            ResultadoMetodo, Serie)
from analise.perfil import Alerta
from analise.valor.central import ValorCentral
from app import formatar_numero, formatar_pct

NAO_ENCONTRADA = "Não encontrei esta ação. Experimenta o ticker (ex.: ASML.AS)."
AVISO_LENTES = "As lentes são interpretações de princípios públicos destes investidores, não as suas opiniões."
RODAPE = "Informação educativa, não é aconselhamento financeiro."
ASML = yahoo.Correspondencia("ASML.AS", "ASML Holding", "Amsterdam", "EQUITY")


@pytest.fixture(autouse=True)
def _limpar_cache():
    import streamlit as st
    st.cache_data.clear()


NB = " "  # espaço não separável: o número não parte a meio no telemóvel


def test_formatar_numero():
    assert formatar_numero(1234.5, "EUR") == f"1{NB}234,50{NB}€"
    assert formatar_numero(1234.5, "USD") == f"1{NB}234,50{NB}USD"
    assert formatar_numero(-1234567.891) == f"-1{NB}234{NB}567,89"
    assert formatar_numero(612.4, "EUR", casas=0) == f"612{NB}€"
    assert formatar_numero(None, "EUR") == "N/D"
    assert formatar_numero(0.0) == "0,00"
    assert formatar_numero(-0.001) == "0,00"


def test_formatar_pct():
    assert formatar_pct(0.15) == f"15,0{NB}%"
    assert formatar_pct(-0.052) == f"-5,2{NB}%"
    assert formatar_pct(12.3456, casas=0) == f"1{NB}235{NB}%"
    assert formatar_pct(None) == "N/D"


def test_pressupostos():
    from app import _pressupostos
    assert _pressupostos({"g": 0.08, "falta": None, "ajustado": True, "fonte": "x"}) == \
        "g: 0,08; falta: N/D; ajustado: Sim; fonte: x"


def _ficha(moeda="EUR", cambio=None, pontuacao=None, central=None):
    f = Fonte("Yahoo Finance", "2026-01-01", "https://example.com")
    sec = Fonte("SEC EDGAR", "2026-01-02", "https://sec.example")
    e = Empresa(ticker="ASML.AS", nome="ASML Holding N.V.", bolsa="Euronext Amsterdam", moeda=moeda,
                pais="Netherlands", setor="Technology", industria="Semiconductors",
                descricao="Faz máquinas de litografia.", preco=Dado(612.4, f),
                capitalizacao=Dado(240e9, f),
                cambio_eur=Dado(cambio, Fonte("BCE (taxas de referência)", "2026-01-04")),
                taxa_sem_risco=Dado(0.025, Fonte("BCE (curva AAA 10 anos)", "2026-01-03", "https://ecb.example")),
                anual={"receita": Serie({2023: 1.0, 2024: 2.0}, sec)},
                avisos=["Receita difere 3,0 % da fonte oficial"], links=[f])
    metodos = [ResultadoMetodo("DCF 2 fases", 705.0, True, pressupostos={"crescimento": 0.08}),
               ResultadoMetodo("P/B bancos", None, False, "Só para bancos")]
    lentes = [ResultadoLente("Buffett", [Criterio("ROE > 15 %", "ok", "25,0 %"),
                                         Criterio("Dívida baixa", "nd", "N/D")], 650.0, "Cumpre 1 de 2", 50.0),
              ResultadoLente("Greenblatt", [], None, "Rank mágico"),
              ResultadoLente("Druckenmiller", [], None, "Momento"),
              ResultadoLente("Graham", [], None, "Faltam dados")]
    p = pontuacao or Pontuacao(81.4, 0.9, "Boa", False,
                               [Componente("valorizacao", 0.3, 90.0, {"margem_seguranca": 0.15}),
                                Componente("tendencia", 0.1, None, {"preco_vs_mm200": None})])
    vc = central or ValorCentral(705.0, 540.0, 860.0, 0.13, 1)
    return servico.Ficha(e, metodos, vc, lentes, p, ("Crescimento", ["CAGR receitas 3 anos: 20,0 %"]),
                         [Alerta("Beta", "1,90", "> 1,80")], "Médio")


def _correr(monkeypatch, ficha, achadas=(ASML,), texto="ASML"):
    monkeypatch.setattr(yahoo, "pesquisar", lambda t: list(achadas))
    monkeypatch.setattr(servico, "analisar", lambda t, ua: ficha)
    at = AppTest.from_file("../app.py").run()
    at.text_input[0].set_value(texto).run()
    assert not at.exception
    return at


def _textos(at):
    blocos = [*at.subheader, *at.markdown, *at.warning, *at.caption, *at.info]
    txt = " ".join([str(e.value) for e in blocos] + [f"{m.label}: {m.value}" for m in at.metric]
                   + [d.value.to_string() for d in at.dataframe])
    return txt.replace(NB, " ")  # o espaço não separável é verificado em test_formatar_numero


def test_app_sem_resultados(monkeypatch):
    at = _correr(monkeypatch, None, achadas=(), texto="xyz")
    assert [w.value for w in at.warning] == [NAO_ENCONTRADA]


def test_app_empresa_nula(monkeypatch):
    at = _correr(monkeypatch, None, achadas=(yahoo.Correspondencia("ZZZ", "Zzz", "X", "EQUITY"),))
    assert [w.value for w in at.warning] == [NAO_ENCONTRADA]


def test_nao_encontrada_nao_fica_em_cache(monkeypatch):
    chamadas = []
    monkeypatch.setattr(yahoo, "pesquisar", lambda t: [ASML])
    monkeypatch.setattr(servico, "analisar", lambda t, ua: chamadas.append(t))
    at = AppTest.from_file("../app.py").run()
    at.text_input[0].set_value("ASML").run()
    at.run()
    assert chamadas == ["ASML.AS", "ASML.AS"]
    assert [w.value for w in at.warning] == [NAO_ENCONTRADA]


def test_ficha_encontrada_fica_em_cache(monkeypatch):
    chamadas = []
    monkeypatch.setattr(yahoo, "pesquisar", lambda t: [ASML])
    monkeypatch.setattr(servico, "analisar", lambda t, ua: chamadas.append(t) or _ficha())
    at = AppTest.from_file("../app.py").run()
    at.text_input[0].set_value("ASML").run()
    at.run()
    assert chamadas == ["ASML.AS"]


@pytest.mark.parametrize("onde", ["pesquisar", "analisar"])
def test_fonte_indisponivel(monkeypatch, onde):
    def falha(*a, **k):
        raise yahoo.FonteIndisponivel()
    monkeypatch.setattr(yahoo, "pesquisar", lambda t: [ASML])
    monkeypatch.setattr(servico, "analisar", lambda t, ua: _ficha())
    monkeypatch.setattr(yahoo if onde == "pesquisar" else servico, onde, falha)
    at = AppTest.from_file("../app.py").run()
    at.text_input[0].set_value("x").run()
    assert [e.value for e in at.error] == ["Yahoo Finance indisponível de momento. Tenta novamente mais tarde."]
    assert not at.warning


def test_app_varios_resultados_usa_radio(monkeypatch):
    outra = yahoo.Correspondencia("ASML", "ASML Holding", "NASDAQ", "EQUITY")
    at = _correr(monkeypatch, _ficha(), achadas=(ASML, outra))
    assert at.radio[0].options == ["ASML Holding · ASML.AS · Amsterdam", "ASML Holding · ASML · NASDAQ"]


def test_app_ficha(monkeypatch):
    at = _correr(monkeypatch, _ficha())
    txt = _textos(at)
    for esperado in ["ASML Holding N.V. · ASML.AS · Euronext Amsterdam · EUR",
                     "Preço: 612,40 €", "Pontuação: 81/100 · Boa", "Risco: Médio",
                     "705,00 €", "540,00 € – 860,00 €", "+13,0 %",
                     "Faz máquinas de litografia.", "Crescimento", "CAGR receitas 3 anos: 20,0 %",
                     "Beta", "Só para bancos", AVISO_LENTES, "sem valor justo", "650,00 €",
                     "Dívida baixa", "N/D", "Fonte: Yahoo Finance, 2026-01-01", "https://example.com",
                     "Fonte: SEC EDGAR, 2026-01-02", "Fonte: BCE (curva AAA 10 anos), 2026-01-03",
                     "Fonte: BCE (taxas de referência), 2026-01-04", "Receita difere 3,0 %", RODAPE]:
        assert esperado in txt, esperado
    assert "**Pontuação: 81/100 · Boa**" in [m.value for m in at.markdown]
    assert [m.label for m in at.metric] == ["Preço", "Risco"]
    rotulos = [e.label for e in at.expander]
    assert rotulos == ["Sobre a empresa", "Crescimento ou valor", "Riscos", "Valor intrínseco",
                       "Lentes", "Pontuação", "Fontes"]
    assert "Conversão para EUR indisponível" not in txt and "≈" not in txt
    # sem valor justo só para Greenblatt e Druckenmiller; Graham sem valor mostra N/D
    assert txt.count("sem valor justo") == 2


def test_app_moeda_estrangeira_mostra_eur(monkeypatch):
    txt = _textos(_correr(monkeypatch, _ficha(moeda="USD", cambio=0.9)))
    assert "Preço: 612,40 USD" in txt
    assert "≈ 551,16 €" in txt


def test_app_sem_cambio(monkeypatch):
    txt = _textos(_correr(monkeypatch, _ficha(moeda="USD", cambio=None)))
    assert "Conversão para EUR indisponível" in txt
    assert "≈" not in txt


@pytest.mark.parametrize("p, esperado", [
    (Pontuacao(None, 0.0, "Sem dados", True, []), "Pontuação: N/D"),
    (Pontuacao(55.6, 0.4, "Fraca", True, []), "Pontuação: 55/100 · Fraca (dados insuficientes)"),
    (Pontuacao(59.6, 0.9, "Fraca", False, []), "Pontuação: 59/100 · Fraca"),
])
def test_app_pontuacao_sem_dados_e_insuficiente(monkeypatch, p, esperado):
    assert esperado in _textos(_correr(monkeypatch, _ficha(pontuacao=p)))


def test_app_sem_valor_central(monkeypatch):
    txt = _textos(_correr(monkeypatch, _ficha(central=ValorCentral(None, None, None, None, 0))))
    assert "Valor intrínseco (central): N/D" in txt
    assert "intervalo" not in txt and "Margem de segurança" not in txt


def test_erro_inesperado_mostra_mensagem(monkeypatch):
    def rebenta(t, ua):
        raise KeyError("x")
    monkeypatch.setattr(yahoo, "pesquisar", lambda t: [ASML])
    monkeypatch.setattr(servico, "analisar", rebenta)
    at = AppTest.from_file("../app.py").run()
    at.text_input[0].set_value("ASML").run()
    assert not at.exception
    assert [e.value for e in at.error] == ["Ocorreu um erro inesperado ao analisar esta ação."]
