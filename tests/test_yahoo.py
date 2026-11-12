import json
from pathlib import Path

import pandas as pd
import pytest

from analise.fontes import yahoo
from analise.modelo import CAMPOS_ANUAIS, Dado, Fonte

FIX = Path(__file__).parent / "fixtures"


def _carregar(nome, converter=lambda de, para: None):
    d = json.loads((FIX / f"yahoo_{nome}.json").read_text(encoding="utf-8"))
    dem = {k: pd.DataFrame(v["data"], index=v["index"],
                           columns=pd.to_datetime(v["columns"]))
           for k, v in d["demonstracoes"].items()}
    precos = pd.Series(d["precos"]["data"], index=pd.to_datetime(d["precos"]["index"]), dtype=float)
    divs = pd.Series(d["dividendos"]["data"], index=pd.to_datetime(d["dividendos"]["index"]), dtype=float)
    return d["info"], yahoo.empresa_de_dados(d["info"], dem, precos, divs, "2026-11-11", converter)


def test_asml_basico():
    info, e = _carregar("ASML.AS")
    assert e.moeda == "EUR"
    assert len(e.anual["receita"].anos()) >= 4
    assert e.preco.valor > 0
    assert e.preco.fonte.nome == "Yahoo Finance"


def test_shel_gbp_e_conversao():
    info, e = _carregar("SHEL.L", lambda de, para: 0.8)
    assert e.moeda == "GBP"
    preco = info.get("currentPrice") or info.get("regularMarketPrice")
    assert e.preco.valor == preco / 100
    assert e.anual["receita"].ultimo() is not None
    _, bruto = _carregar("SHEL.L", lambda de, para: 1.0)
    assert e.anual["receita"].ultimo() == bruto.anual["receita"].ultimo() * 0.8
    assert e.anual["acoes_media"].ultimo() == bruto.anual["acoes_media"].ultimo()


def test_sem_conversao_avisa():
    _, e = _carregar("SHEL.L")
    assert set(e.anual) == set(CAMPOS_ANUAIS)
    assert e.anual["receita"].anos() == []
    assert e.anual["acoes_media"].anos() != []
    assert any("sem conversão disponível" in a for a in e.avisos)
    assert e.preco.valor > 0


def test_balancos_vazios():
    _, e = _carregar("vazio")
    assert e.preco.valor == 10.0
    assert set(e.anual) == set(CAMPOS_ANUAIS)
    assert all(s.anos() == [] for s in e.anual.values())
    assert e.dividendos == {}


def test_capex_positivo():
    _, e = _carregar("AAPL")
    assert e.anual["capex"].ultimo() > 0


def test_pesquisar_sem_resultados(monkeypatch):
    class S:
        def __init__(self, *a, **k):
            self.quotes = []
    monkeypatch.setattr(yahoo.yf, "Search", S)
    assert yahoo.pesquisar("xyz") == []


def test_pesquisar_falha_levanta(monkeypatch):
    class S:
        def __init__(self, *a, **k):
            raise RuntimeError("rede")
    monkeypatch.setattr(yahoo.yf, "Search", S)
    with pytest.raises(yahoo.FonteIndisponivel):
        yahoo.pesquisar("xyz")


def test_conversor_chamado_uma_vez():
    chamadas = []

    def conv(de, para):
        chamadas.append((de, para))
        return 0.5
    _carregar("ASML.AS", conv)
    assert len(chamadas) <= 1


def test_capitalizacao_em_gbp():
    info, e = _carregar("SHEL.L")
    assert abs(e.capitalizacao.valor / (e.preco.valor * e.acoes.valor) - 1) < 0.05


def test_carregar_empresa_info_falha(monkeypatch):
    class T:
        def __init__(self, *a):
            pass

        @property
        def info(self):
            raise RuntimeError("rede")
    monkeypatch.setattr(yahoo.yf, "Ticker", T)
    with pytest.raises(yahoo.FonteIndisponivel):
        yahoo.carregar_empresa("X")


def test_carregar_empresa_historico_vazio(monkeypatch):
    class T:
        info = {"currentPrice": 5.0, "currency": "EUR"}
        income_stmt = balance_sheet = cash_flow = pd.DataFrame()
        dividends = pd.Series(dtype=float)

        def __init__(self, *a):
            pass

        def history(self, **k):
            return pd.DataFrame()
    monkeypatch.setattr(yahoo.yf, "Ticker", T)
    monkeypatch.setattr(yahoo.taxas, "taxa_sem_risco", lambda m, h: (Dado(0.03, Fonte("t", h)), None))
    monkeypatch.setattr(yahoo.taxas, "para_eur", lambda m: Dado(1.0, Fonte("t", "2026-11-11")))
    e = yahoo.carregar_empresa("X", converter=lambda de, para: None)
    assert e.preco.valor == 5.0 and e.precos.empty
    assert e.taxa_sem_risco.valor == 0.03 and e.cambio_eur.valor == 1.0 and e.avisos == []


def test_carregar_empresa_aviso_taxa_defeito(monkeypatch):
    class T:
        info = {"currentPrice": 5.0, "currency": "EUR"}
        income_stmt = balance_sheet = cash_flow = pd.DataFrame()
        dividends = pd.Series(dtype=float)

        def __init__(self, *a):
            pass

        def history(self, **k):
            return pd.DataFrame()
    monkeypatch.setattr(yahoo.yf, "Ticker", T)
    monkeypatch.setattr(yahoo.taxas, "taxa_sem_risco", lambda m, h: (Dado(0.027, Fonte("t", h)), "defeito"))
    monkeypatch.setattr(yahoo.taxas, "para_eur", lambda m: Dado(None, Fonte("t", "2026-11-11")))
    e = yahoo.carregar_empresa("X")
    assert "defeito" in e.avisos and e.cambio_eur.valor is None


def test_pesquisar_repete_sem_acentos(monkeypatch):
    pedidos = []

    class S:
        def __init__(self, texto, *a, **k):
            pedidos.append(texto)
            self.quotes = ([{"symbol": "JMT.LS", "longname": "Jerónimo Martins", "exchDisp": "Lisbon",
                             "quoteType": "EQUITY"}] if texto == "Jeronimo Martins" else [])
    monkeypatch.setattr(yahoo.yf, "Search", S)
    r = yahoo.pesquisar("Jerónimo Martins")
    assert pedidos == ["Jerónimo Martins", "Jeronimo Martins"]
    assert [c.ticker for c in r] == ["JMT.LS"]


def test_pesquisar_sem_acentos_nao_repete(monkeypatch):
    pedidos = []

    class S:
        def __init__(self, texto, *a, **k):
            pedidos.append(texto)
            self.quotes = []
    monkeypatch.setattr(yahoo.yf, "Search", S)
    assert yahoo.pesquisar("xyz") == []
    assert pedidos == ["xyz"]
