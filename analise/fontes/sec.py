from datetime import date, datetime
from functools import lru_cache

import requests

from analise.modelo import Empresa, Fonte, Serie

_URL_TICKERS = "https://www.sec.gov/files/company_tickers.json"
_URL_FACTOS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_BOLSAS_EUA = {"NMS", "NYQ", "NGM", "NCM", "ASE", "PCX",  # códigos Yahoo
               "NasdaqGS", "NasdaqGM", "NasdaqCM", "NYSE", "NYSEArca", "NYSE American"}
_TAGS = {  # campo -> (tags por prioridade, unidade)
    "receita": (("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"), "USD"),
    "lucro_liquido": (("NetIncomeLoss",), "USD"),
    "fluxo_operacional": (("NetCashProvidedByUsedInOperatingActivities",), "USD"),
    "capex": (("PaymentsToAcquirePropertyPlantAndEquipment",), "USD"),
    "eps": (("EarningsPerShareDiluted",), "USD/shares"),
    "acoes_media": (("WeightedAverageNumberOfDilutedSharesOutstanding",), "shares"),
    "ebit": (("OperatingIncomeLoss",), "USD"),
    "capital_proprio": (("StockholdersEquity",), "USD"),
    "dividendos": (("CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"), "USD/shares"),
}


def _anual(factos: list[dict]) -> dict[int, float]:
    """Ano do fim do período -> valor do 10-K (ou 10-K/A) mais recentemente arquivado."""
    melhor: dict[int, dict] = {}
    for f in factos:
        if f.get("form") not in ("10-K", "10-K/A") or f.get("fp") != "FY":
            continue
        if "start" in f:  # fluxos: só períodos de ~1 ano (balanço não tem start)
            dias = (datetime.fromisoformat(f["end"]) - datetime.fromisoformat(f["start"])).days
            if not 330 <= dias <= 400:
                continue
        ano = int(f["end"][:4])
        if ano not in melhor or f["filed"] > melhor[ano]["filed"]:
            melhor[ano] = f
    return {a: f["val"] for a, f in melhor.items()}


def series_de_companyfacts(dados: dict, hoje: str, cik: str) -> dict[str, Serie]:
    """Séries anuais (e "dividendos" por ação) dos 10-K; a 1.ª tag manda, as seguintes preenchem anos em falta."""
    gaap = dados.get("facts", {}).get("us-gaap", {})
    fonte = Fonte("SEC EDGAR (10-K)", hoje,
                  f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K")
    out: dict[str, Serie] = {}
    for campo, (tags, unidade) in _TAGS.items():
        valores: dict[int, float] = {}
        for tag in tags:
            for ano, v in _anual(gaap.get(tag, {}).get("units", {}).get(unidade, [])).items():
                valores.setdefault(ano, v)
        if valores:
            out[campo] = Serie(valores, fonte)
    if "fluxo_operacional" in out and "capex" in out:
        op, cx = out["fluxo_operacional"].valores, out["capex"].valores
        out["fcf"] = Serie({a: op[a] - cx[a] for a in op if a in cx}, fonte)
    return out


@lru_cache(maxsize=None)
def _mapa_tickers(user_agent: str) -> dict[str, str]:
    """ticker -> CIK (10 dígitos). Levanta em falha (lru_cache não guarda exceções)."""
    r = requests.get(_URL_TICKERS, headers={"User-Agent": user_agent}, timeout=15)
    r.raise_for_status()
    return {v["ticker"].upper(): f"{v['cik_str']:010d}" for v in r.json().values()}


def cik_de(ticker: str, user_agent: str) -> str | None:
    return _mapa_tickers(user_agent).get(ticker.upper())


def enriquecer(e: Empresa, user_agent: str | None) -> Empresa:
    """Completa `e` com o histórico da SEC (só EUA). Altera e devolve a mesma Empresa."""
    if e.bolsa not in _BOLSAS_EUA:
        return e
    if not user_agent:
        e.avisos.append("SEC não configurada")
        return e
    hoje = date.today().isoformat()
    try:
        cik = cik_de(e.ticker, user_agent)
        if cik is None:
            return e
        r = requests.get(_URL_FACTOS.format(cik=cik), headers={"User-Agent": user_agent}, timeout=15)
        r.raise_for_status()
        series = series_de_companyfacts(r.json(), hoje, cik)
    except (requests.RequestException, ValueError):
        e.avisos.append("SEC indisponível")
        return e
    usou = False
    for campo, s in series.items():
        # só substitui se a SEC tem mais anos e não está desatualizada face ao atual
        if campo == "dividendos":
            atual = e.dividendos
            if len(s.anos()) > len(atual) and max(s.anos()) >= max(atual, default=0):
                e.dividendos, usou = dict(s.valores), True
            continue
        yahoo = e.anual.get(campo)
        if yahoo is None or (len(s.anos()) > len(yahoo.anos())
                             and max(s.anos()) >= max(yahoo.anos(), default=0)):
            e.anual[campo], usou = s, True
    if usou:
        e.links.append(next(iter(series.values())).fonte)
    return e
