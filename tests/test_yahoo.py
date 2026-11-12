import json
from pathlib import Path

import pandas as pd

from analise.fontes import yahoo

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
    assert "receita" not in e.anual or e.anual["receita"].ultimo() is None
    assert any("sem conversão disponível" in a for a in e.avisos)
    assert e.preco.valor > 0


def test_balancos_vazios():
    _, e = _carregar("vazio")
    assert e.preco.valor == 10.0
    assert all(s.ultimo() is None for s in e.anual.values())


def test_capex_positivo():
    _, e = _carregar("AAPL")
    assert e.anual["capex"].ultimo() > 0


def test_pesquisar_sem_resultados(monkeypatch):
    class S:
        def __init__(self, *a, **k):
            self.quotes = []
    monkeypatch.setattr(yahoo.yf, "Search", S)
    assert yahoo.pesquisar("xyz") == []
