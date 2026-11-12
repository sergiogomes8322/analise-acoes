import csv
import io
import time
from datetime import date
from functools import lru_cache

import requests
import yfinance as yf

from analise import config
from analise.modelo import Dado, Fonte

_BCE = "https://data-api.ecb.europa.eu/service/data/"
_RENDIMENTO_EUR = _BCE + "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?lastNObservations=1&format=csvdata"


def _ler_csv_bce(texto: str) -> float | None:
    """Última OBS_VALUE de um CSV do BCE; None se vazio ou ilegível."""
    linhas = list(csv.DictReader(io.StringIO(texto)))
    try:
        return float(linhas[-1]["OBS_VALUE"])
    except (IndexError, KeyError, ValueError):
        return None


def _url_cambio(moeda: str) -> str:
    return f"{_BCE}EXR/D.{moeda}.EUR.SP00.A?lastNObservations=1&format=csvdata"


@lru_cache(maxsize=None)
def _taxa_bce(moeda: str) -> float:
    """Unidades de `moeda` por 1 EUR. Levanta em falha (lru_cache não guarda exceções)."""
    r = requests.get(_url_cambio(moeda), timeout=10)
    r.raise_for_status()
    valor = _ler_csv_bce(r.text)
    if not valor:
        raise ValueError(f"sem taxa BCE para {moeda}")
    return valor


_FALHAS: dict[str, float] = {}  # moeda -> instante (monotonic) da última falha
_PAUSA_S = 300


def _taxa(moeda: str) -> float | None:
    if moeda == "EUR":
        return 1.0
    falhou = _FALHAS.get(moeda)
    if falhou is not None and time.monotonic() - falhou < _PAUSA_S:
        return None  # BCE em baixo: não repetir o timeout de 10 s a cada chamada
    try:
        return _taxa_bce(moeda)
    except (requests.RequestException, ValueError):
        _FALHAS[moeda] = time.monotonic()
        return None


def cambio(de: str, para: str) -> float | None:
    if de == para:
        return 1.0
    r_de, r_para = _taxa(de), _taxa(para)
    return None if r_de is None or r_para is None else r_para / r_de


def para_eur(moeda: str) -> Dado:
    taxa = _taxa(moeda)
    fonte = Fonte("BCE (taxas de referência)", date.today().isoformat(), _url_cambio(moeda))
    return Dado(None if taxa is None else 1 / taxa, fonte)


def _rendimento(moeda: str, hoje: str) -> tuple[float, Fonte] | None:
    """Rendimento a 10 anos (fração) e fonte; None em falha."""
    if moeda == "EUR":
        try:
            r = requests.get(_RENDIMENTO_EUR, timeout=10)
            r.raise_for_status()
        except requests.RequestException:
            return None
        v = _ler_csv_bce(r.text)
        return None if v is None else (v / 100, Fonte("BCE (curva de rendimentos 10A)", hoje, _RENDIMENTO_EUR))
    if moeda == "USD":
        try:
            fecho = yf.Ticker("^TNX").history(period="5d")["Close"].dropna()
            return float(fecho.iloc[-1]) / 100, Fonte("Yahoo Finance (^TNX)", hoje, "https://finance.yahoo.com/quote/%5ETNX")
        except Exception:  # yfinance levanta tipos próprios; fonte secundária, nunca propaga
            return None
    return None


def taxa_sem_risco(moeda: str, hoje: str) -> tuple[Dado, str | None]:
    obtido = _rendimento(moeda, hoje)
    if obtido is not None:
        return Dado(obtido[0], obtido[1]), None
    cfg = config.carregar()["sem_risco_defeito"]
    return (Dado(cfg.get(moeda, cfg["OUTRA"]), Fonte("Valor por defeito (config.toml)", cfg["data"])),
            f"Taxa sem risco por defeito (definida em {cfg['data']})")
