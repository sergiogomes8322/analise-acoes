from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from analise.modelo import Dado, Empresa, Fonte, Serie

MAPA = {
    "receita": "Total Revenue", "lucro_bruto": "Gross Profit", "ebit": "EBIT",
    "ebitda": "EBITDA", "lucro_liquido": "Net Income",
    "resultado_antes_impostos": "Pretax Income", "impostos": "Tax Provision",
    "despesa_juros": "Interest Expense",
    "amortizacoes": "Depreciation And Amortization",
    "fluxo_operacional": "Operating Cash Flow", "capex": "Capital Expenditure",
    "fcf": "Free Cash Flow", "eps": "Diluted EPS",
    "acoes_media": "Diluted Average Shares", "ativo_total": "Total Assets",
    "ativo_corrente": "Current Assets", "passivo_corrente": "Current Liabilities",
    "passivo_total": "Total Liabilities Net Minority Interest",
    "divida_total": "Total Debt", "divida_longo_prazo": "Long Term Debt",
    "caixa": "Cash And Cash Equivalents", "capital_proprio": "Stockholders Equity",
    "lucros_retidos": "Retained Earnings", "imobilizado": "Net PPE",
}
_ORIGEM = {  # campo -> demonstração onde está o rótulo
    **dict.fromkeys(list(MAPA)[:14], "income"),
    "fluxo_operacional": "cashflow", "capex": "cashflow", "fcf": "cashflow",
    "amortizacoes": "cashflow",
    **dict.fromkeys(list(MAPA)[14:], "balance"),
}
_SUBUNIDADES = {"GBp": "GBP", "ZAc": "ZAR", "ILA": "ILS"}


@dataclass
class Correspondencia:
    ticker: str
    nome: str
    bolsa: str
    tipo: str


def pesquisar(texto: str) -> list[Correspondencia]:
    try:
        quotes = yf.Search(texto).quotes
    except Exception:
        return []
    return [Correspondencia(q["symbol"], q.get("longname") or q.get("shortname") or "",
                            q.get("exchDisp") or q.get("exchange") or "", q["quoteType"])
            for q in quotes if q.get("quoteType") == "EQUITY" and q.get("symbol")]


def _serie(df: pd.DataFrame | None, rotulo: str, fonte: Fonte, fator: float, absoluto: bool) -> Serie | None:
    if df is None or rotulo not in df.index:
        return None
    valores = {}
    for data, v in df.loc[rotulo].items():
        if pd.notna(v):
            v = float(v) * fator
            valores[pd.Timestamp(data).year] = abs(v) if absoluto else v
    return Serie(valores, fonte)


def empresa_de_dados(info: dict, demonstracoes: dict[str, pd.DataFrame], precos: pd.Series,
                     dividendos: pd.Series, hoje: str,
                     converter: Callable[[str, str], float | None] = lambda de, para: None) -> Empresa:
    ticker = info.get("symbol", "")
    fonte = Fonte("Yahoo Finance", hoje, f"https://finance.yahoo.com/quote/{ticker}")
    cotacao = info.get("currency") or ""
    div = 100.0 if cotacao in _SUBUNIDADES else 1.0
    moeda = _SUBUNIDADES.get(cotacao, cotacao)
    avisos: list[str] = []

    preco = next((info[k] for k in ("currentPrice", "regularMarketPrice", "previousClose")
                  if info.get(k) is not None), None)
    setor, industria = info.get("sector") or "", info.get("industry") or ""
    e = Empresa(
        ticker=ticker, nome=info.get("longName") or info.get("shortName") or ticker,
        bolsa=info.get("fullExchangeName") or info.get("exchange") or "", moeda=moeda,
        pais=info.get("country") or "", setor=setor, industria=industria,
        descricao=info.get("longBusinessSummary") or "",
        e_financeira=setor == "Financial Services" and any(p in industria for p in ("Bank", "Insurance")),
        preco=Dado(None if preco is None else preco / div, fonte),
        acoes=Dado(info.get("sharesOutstanding"), fonte),
        beta=Dado(info.get("beta"), fonte),
        capitalizacao=Dado(info.get("marketCap"), fonte)  # Yahoo já dá a capitalização em GBP, não em GBp,
        precos=(precos / div).dropna(), avisos=avisos, links=[fonte],
    )

    financeira = info.get("financialCurrency") or moeda
    taxa = 1.0 if financeira == moeda else converter(financeira, moeda)
    if taxa is None:
        avisos.append(f"Balanços em {financeira} sem conversão disponível")
    for campo, rotulo in MAPA.items():
        monetario = campo != "acoes_media"
        if monetario and taxa is None:
            continue
        s = _serie(demonstracoes.get(_ORIGEM[campo]), rotulo, fonte,
                   taxa if monetario else 1.0, campo == "capex")
        if s is not None:
            e.anual[campo] = s

    ano = int(hoje[:4])
    por_ano = (dividendos / div).groupby(dividendos.index.year).sum()
    e.dividendos = {int(a): float(v) for a, v in por_ano.items() if a < ano}
    return e


def carregar_empresa(ticker: str, converter: Callable[[str, str], float | None] = lambda de, para: None) -> Empresa | None:
    from datetime import date
    t = yf.Ticker(ticker)
    info = {**t.info, "symbol": ticker}
    if not any(info.get(k) for k in ("currentPrice", "regularMarketPrice", "previousClose")):
        return None
    dem = {"income": t.income_stmt, "balance": t.balance_sheet, "cashflow": t.cash_flow}
    return empresa_de_dados(info, dem, t.history(period="5y")["Close"], t.dividends,
                            date.today().isoformat(), converter)
