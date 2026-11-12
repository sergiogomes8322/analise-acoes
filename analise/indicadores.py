import math
import statistics

import pandas as pd

from analise.config import carregar
from analise.modelo import Empresa, Serie


def escala(x: float | None, zero: float, cem: float) -> float | None:
    """Interpolacao linear limitada a [0, 100]; zero > cem inverte a escala."""
    if x is None:
        return None
    return max(0.0, min(100.0, (x - zero) / (cem - zero) * 100.0))

DIAS_MES = 21


def _v(e: Empresa, campo: str, ano: int) -> float | None:
    s = e.anual.get(campo)
    x = s.valores.get(ano) if s else None
    return None if x is None or math.isnan(x) else x


def _anos(e: Empresa, campo: str) -> list[int]:
    s = e.anual.get(campo)
    return s.anos() if s else []


def _ultimo_ano(e: Empresa, campo: str) -> int | None:
    anos = _anos(e, campo)
    return anos[-1] if anos else None


def _div(a: float | None, b: float | None) -> float | None:
    return None if a is None or not b else a / b


def cagr(serie: Serie, anos_max: int) -> tuple[float | None, int]:
    pts = serie._validos()[-(anos_max + 1):]
    if len(pts) < 2:
        return None, 0
    (a0, v0), (a1, v1) = pts[0], pts[-1]
    n = a1 - a0
    if v0 <= 0 or v1 <= 0 or n <= 0:
        return None, n
    return (v1 / v0) ** (1 / n) - 1, n


def media(valores: list[float]) -> float | None:
    return sum(valores) / len(valores) if valores else None


def coef_variacao(valores: list[float]) -> float | None:
    m = media(valores)
    if len(valores) < 2 or not m:
        return None
    return statistics.stdev(valores) / abs(m)


def fracao_anos_a_crescer(serie: Serie) -> float | None:
    v = [x for _, x in serie._validos()]
    if len(v) < 2:
        return None
    return sum(b > a for a, b in zip(v, v[1:])) / (len(v) - 1)


def _limpa(precos: pd.Series) -> pd.Series:
    return precos.dropna().reset_index(drop=True)


def volatilidade_anual(precos: pd.Series) -> float | None:
    r = _limpa(precos).pct_change().dropna().tail(252)
    return float(r.std() * math.sqrt(252)) if len(r) >= 2 else None


def queda_maxima(precos: pd.Series) -> float | None:
    p = _limpa(precos)
    if p.empty:
        return None
    return float((1 - p / p.cummax()).max())


def preco_vs_mm200(precos: pd.Series) -> float | None:
    p = _limpa(precos)
    if len(p) < 200:
        return None
    mm = float(p.tail(200).mean())
    return float(p.iloc[-1]) / mm - 1 if mm else None


def momento(precos: pd.Series, meses: int, saltar_meses: int = 0) -> float | None:
    p = _limpa(precos)
    fim = len(p) - 1 - saltar_meses * DIAS_MES
    ini = len(p) - 1 - meses * DIAS_MES
    if ini < 0 or fim <= ini or p.iloc[ini] <= 0:
        return None
    return float(p.iloc[fim] / p.iloc[ini] - 1)


def taxa_imposto(e: Empresa) -> float:
    taxas = [t / r for a in _anos(e, "resultado_antes_impostos")
             if (r := _v(e, "resultado_antes_impostos", a)) and r > 0
             and (t := _v(e, "impostos", a)) is not None]
    if not taxas:
        return carregar()["impostos"]["taxa_defeito"]
    return min(0.5, max(0.0, sum(taxas) / len(taxas)))


def roic(e: Empresa, ano: int) -> float | None:
    ebit, cp, d, c = (_v(e, k, ano) for k in ("ebit", "capital_proprio", "divida_total", "caixa"))
    if None in (ebit, cp, d, c):
        return None
    capital = cp + d - c
    return ebit * (1 - taxa_imposto(e)) / capital if capital > 0 else None


def roe(e: Empresa, ano: int) -> float | None:
    ll, cp = _v(e, "lucro_liquido", ano), _v(e, "capital_proprio", ano)
    return ll / cp if ll is not None and cp and cp > 0 else None


def margem_operacional(e: Empresa, ano: int) -> float | None:
    return _div(_v(e, "ebit", ano), _v(e, "receita", ano))


def divida_liquida_ebitda(e: Empresa) -> float | None:
    ano = _ultimo_ano(e, "ebitda")
    if ano is None:
        return None
    ebitda, d, c = _v(e, "ebitda", ano), _v(e, "divida_total", ano), _v(e, "caixa", ano)
    return (d - c) / ebitda if ebitda > 0 and d is not None and c is not None else None


def cobertura_juros(e: Empresa) -> float | None:
    ano = _ultimo_ano(e, "ebit")
    if ano is None:
        return None
    j = _v(e, "despesa_juros", ano)
    return _div(_v(e, "ebit", ano), abs(j) if j else None)


def altman_z(e: Empresa) -> float | None:
    ano = _ultimo_ano(e, "ativo_total")
    if ano is None:
        return None
    ta, tl = _v(e, "ativo_total", ano), _v(e, "passivo_total", ano)
    ac, pc, re, ebit, vendas = (_v(e, k, ano) for k in (
        "ativo_corrente", "passivo_corrente", "lucros_retidos", "ebit", "receita"))
    mve = e.capitalizacao.valor
    if None in (tl, ac, pc, re, ebit, vendas, mve) or ta <= 0 or tl <= 0:
        return None
    return (1.2 * (ac - pc) / ta + 1.4 * re / ta + 3.3 * ebit / ta
            + 0.6 * mve / tl + 1.0 * vendas / ta)


def piotroski_f(e: Empresa) -> int | None:
    comuns = sorted(set(_anos(e, "lucro_liquido")) & set(_anos(e, "ativo_total")))
    if len(comuns) < 2:
        return None
    a0, a1 = comuns[-2:]

    def r(num: str, den: str, a: int) -> float | None:
        return _div(_v(e, num, a), _v(e, den, a))

    def cr(a: int) -> float | None:
        return _div(_v(e, "ativo_corrente", a), _v(e, "passivo_corrente", a))

    def sobe(f, a: int, b: int) -> bool:
        x, y = f(a), f(b)
        return x is not None and y is not None and y > x

    cfo, ll, ac0, ac1 = _v(e, "fluxo_operacional", a1), _v(e, "lucro_liquido", a1), \
        _v(e, "acoes_media", a0), _v(e, "acoes_media", a1)
    roa = lambda a: r("lucro_liquido", "ativo_total", a)
    lev = lambda a: r("divida_longo_prazo", "ativo_total", a)
    sinais = [
        (roa(a1) or 0) > 0,
        cfo is not None and cfo > 0,
        sobe(roa, a0, a1),
        cfo is not None and cfo > ll,
        sobe(lev, a1, a0),
        sobe(cr, a0, a1),
        ac0 is not None and ac1 is not None and ac1 <= ac0,
        sobe(lambda a: r("lucro_bruto", "receita", a), a0, a1),
        sobe(lambda a: r("receita", "ativo_total", a), a0, a1),
    ]
    return sum(sinais)


def diluicao_anual(e: Empresa) -> float | None:
    s = e.anual.get("acoes_media")
    return cagr(s, carregar()["historico"]["anos_pedidos"])[0] if s else None
