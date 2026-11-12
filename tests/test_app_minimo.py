import pytest
from streamlit.testing.v1 import AppTest

from analise.fontes import yahoo
from analise.modelo import Dado, Empresa, Fonte, Serie

NAO_ENCONTRADA = "Não encontrei esta ação. Experimenta o ticker (ex.: ASML.AS)."


@pytest.fixture(autouse=True)
def _limpar_cache():
    import streamlit as st
    st.cache_data.clear()


def _empresa():
    f = Fonte("Yahoo Finance", "2026-01-01", "https://example.com")
    return Empresa(ticker="ASML.AS", nome="ASML Holding N.V.", bolsa="Amsterdam", moeda="EUR",
                   preco=Dado(700.5, f), anual={"receita": Serie({2022: 1.0, 2023: 2.0, 2024: 3.0}, f)})


def _textos(at):
    return " ".join(str(e.value) for e in [*at.subheader, *at.markdown, *at.warning, *at.metric])


def test_mostra_correspondencias_e_empresa(monkeypatch):
    monkeypatch.setattr(yahoo, "pesquisar", lambda t: [yahoo.Correspondencia("ASML.AS", "ASML Holding", "Amsterdam", "EQUITY")])
    monkeypatch.setattr(yahoo, "carregar_empresa", lambda t, **k: _empresa())
    at = AppTest.from_file("../app.py").run()
    at.text_input[0].set_value("ASML").run()
    assert not at.exception
    assert at.selectbox[0].options and "ASML.AS" in at.selectbox[0].options[0]
    txt = _textos(at)
    assert "ASML Holding N.V." in txt and "700.5" in txt and "EUR" in txt
    assert "3" in txt


def test_sem_correspondencias(monkeypatch):
    monkeypatch.setattr(yahoo, "pesquisar", lambda t: [])
    at = AppTest.from_file("../app.py").run()
    at.text_input[0].set_value("xyz").run()
    assert [w.value for w in at.warning] == [NAO_ENCONTRADA]


def test_empresa_nula(monkeypatch):
    monkeypatch.setattr(yahoo, "pesquisar", lambda t: [yahoo.Correspondencia("ZZZ", "Zzz", "X", "EQUITY")])
    monkeypatch.setattr(yahoo, "carregar_empresa", lambda t, **k: None)
    at = AppTest.from_file("../app.py").run()
    at.text_input[0].set_value("zzz").run()
    assert [w.value for w in at.warning] == [NAO_ENCONTRADA]
