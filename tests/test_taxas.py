from pathlib import Path

import pandas as pd
import pytest
import requests

from analise import config
from analise.fontes import taxas

FIX = Path(__file__).parent / "fixtures"


def _csv(nome):
    return (FIX / nome).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _sem_cache():
    taxas._taxa_bce.cache_clear()
    taxas._FALHAS.clear()
    yield
    taxas._taxa_bce.cache_clear()
    taxas._FALHAS.clear()


def _sem_rede(monkeypatch):
    def falha(*a, **k):
        raise requests.ConnectionError("sem rede")
    monkeypatch.setattr(taxas.requests, "get", falha)


def test_ler_csv_bce_gravados():
    assert taxas._ler_csv_bce(_csv("bce_eur10y.csv")) == pytest.approx(3.3308865271)
    assert taxas._ler_csv_bce(_csv("bce_usd.csv")) == pytest.approx(1.1127)
    assert taxas._ler_csv_bce(_csv("bce_gbp.csv")) == pytest.approx(0.83618)


def test_ler_csv_bce_invalido():
    assert taxas._ler_csv_bce("") is None
    assert taxas._ler_csv_bce("KEY,OBS_VALUE\n") is None
    assert taxas._ler_csv_bce("KEY,OBS_VALUE\nx,abc\n") is None


def test_cambio_cruzado_via_eur(monkeypatch):
    monkeypatch.setattr(taxas, "_taxa_bce", {"USD": 1.1127, "GBP": 0.83618}.__getitem__)
    assert taxas.cambio("USD", "GBP") == pytest.approx(0.83618 / 1.1127)
    assert taxas.cambio("EUR", "USD") == pytest.approx(1.1127)
    assert taxas.cambio("USD", "USD") == 1.0


def test_cambio_sem_rede_devolve_none(monkeypatch):
    _sem_rede(monkeypatch)
    assert taxas.cambio("USD", "GBP") is None
    assert taxas.cambio("EUR", "EUR") == 1.0


def test_para_eur(monkeypatch):
    monkeypatch.setattr(taxas, "_taxa_bce", lambda m: 1.1127)
    d = taxas.para_eur("USD")
    assert d.valor == pytest.approx(1 / 1.1127) and "BCE" in d.fonte.nome and "USD" in d.fonte.url
    assert taxas.para_eur("EUR").valor == 1.0


def test_para_eur_sem_rede(monkeypatch):
    _sem_rede(monkeypatch)
    assert taxas.para_eur("USD").valor is None


def test_taxa_bce_usa_timeout_e_cache(monkeypatch):
    chamadas = []

    class R:
        text = _csv("bce_usd.csv")

        def raise_for_status(self):
            pass

    def get(url, timeout):
        chamadas.append(timeout)
        return R()
    monkeypatch.setattr(taxas.requests, "get", get)
    assert taxas._taxa_bce("USD") == taxas._taxa_bce("USD") == pytest.approx(1.1127)
    assert chamadas == [10]


def test_taxa_sem_risco_eur(monkeypatch):
    class R:
        text = _csv("bce_eur10y.csv")

        def raise_for_status(self):
            pass
    monkeypatch.setattr(taxas.requests, "get", lambda url, timeout: R())
    d, aviso = taxas.taxa_sem_risco("EUR", "2026-11-11")
    assert d.valor == pytest.approx(0.033308865271) and aviso is None and "BCE" in d.fonte.nome


def test_taxa_sem_risco_usd(monkeypatch):
    class T:
        def __init__(self, s):
            assert s == "^TNX"

        def history(self, **k):
            return pd.DataFrame({"Close": [4.0, 4.2]})
    monkeypatch.setattr(taxas.yf, "Ticker", T)
    d, aviso = taxas.taxa_sem_risco("USD", "2026-11-11")
    assert d.valor == pytest.approx(0.042) and aviso is None


def test_taxa_sem_risco_rede_falha_usa_defeito(monkeypatch):
    _sem_rede(monkeypatch)
    cfg = config.carregar()["sem_risco_defeito"]
    d, aviso = taxas.taxa_sem_risco("EUR", "2026-11-11")
    assert d.valor == cfg["EUR"] and aviso == f"Taxa sem risco por defeito (definida em {cfg['data']})"


def test_taxa_sem_risco_yfinance_falha(monkeypatch):
    class T:
        def __init__(self, s):
            raise RuntimeError("yahoo")
    monkeypatch.setattr(taxas.yf, "Ticker", T)
    d, aviso = taxas.taxa_sem_risco("USD", "2026-11-11")
    assert d.valor == config.carregar()["sem_risco_defeito"]["USD"] and aviso


def test_falha_nao_repete_pedido_na_janela(monkeypatch):
    chamadas = []

    def falha(url, timeout):
        chamadas.append(url)
        raise requests.ConnectionError("sem rede")
    monkeypatch.setattr(taxas.requests, "get", falha)
    for _ in range(5):
        assert taxas.cambio("USD", "EUR") is None
    assert taxas.para_eur("USD").valor is None
    assert len(chamadas) == 1


def test_retry_depois_da_pausa(monkeypatch):
    relogio = [1000.0]
    monkeypatch.setattr(taxas.time, "monotonic", lambda: relogio[0])
    estado = {"falha": True}

    class R:
        text = _csv("bce_usd.csv")

        def raise_for_status(self):
            pass

    def get(url, timeout):
        if estado["falha"]:
            raise requests.ConnectionError("sem rede")
        return R()
    monkeypatch.setattr(taxas.requests, "get", get)
    assert taxas._taxa("USD") is None
    estado["falha"] = False
    relogio[0] += 299
    assert taxas._taxa("USD") is None  # ainda na pausa
    relogio[0] += 2
    assert taxas._taxa("USD") == pytest.approx(1.1127)


def test_taxa_sem_risco_outra_moeda():
    cfg = config.carregar()["sem_risco_defeito"]
    d, aviso = taxas.taxa_sem_risco("GBP", "2026-11-11")
    assert d.valor == cfg["GBP"] and aviso
    d, _ = taxas.taxa_sem_risco("JPY", "2026-11-11")
    assert d.valor == cfg["OUTRA"]


def test_para_eur_eur_sem_url(monkeypatch):
    _sem_rede(monkeypatch)
    d = taxas.para_eur("EUR")
    assert d.valor == 1.0 and d.fonte.nome == "" and d.fonte.url is None
