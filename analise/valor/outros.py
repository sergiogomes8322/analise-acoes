import math
import statistics

import pandas as pd

from analise.config import carregar
from analise.indicadores import _anos, _ultimo_ano, _v, cagr, media, roe, taxa_imposto
from analise.modelo import Empresa, ResultadoMetodo, Serie
from analise.valor.dcf import dcf, owner_earnings, taxa_desconto


def _nao(nome: str, motivo: str) -> ResultadoMetodo:
    return ResultadoMetodo(nome, None, False, motivo)


def _ult(e: Empresa, campo: str) -> float | None:
    ano = _ultimo_ano(e, campo)
    return _v(e, campo, ano) if ano else None


def _bvps(e: Empresa) -> float | None:
    cp = _ult(e, "capital_proprio")
    return cp / e.acoes.valor if cp is not None and e.acoes.valor else None


def formula_graham(e: Empresa) -> ResultadoMetodo:
    nome = "Fórmula de Graham"
    eps = _ult(e, "eps")
    if eps is None:
        return _nao(nome, "Sem dados suficientes")
    if eps <= 0:
        return _nao(nome, "EPS negativo ou nulo")
    c = carregar()
    s = e.anual.get("eps") if cagr(e.anual["eps"], 5)[0] is not None else e.anual.get("receita")
    taxa = cagr(s, 5)[0] if s else None
    g = min(max((taxa or 0.0) * 100, 0.0), c["graham"]["g_max"])
    rf = e.taxa_sem_risco.valor
    if rf is None:
        d = c["sem_risco_defeito"]
        rf = d.get(e.moeda, d["OUTRA"])
    y = (rf + c["graham"]["spread_aaa"]) * 100
    return ResultadoMetodo(nome, eps * (8.5 + 2 * g) * 4.4 / y, True,
                           pressupostos={"eps": eps, "g": g, "Y": y})


def numero_graham(e: Empresa) -> ResultadoMetodo:
    nome = "Número de Graham"
    eps, bvps = _ult(e, "eps"), _bvps(e)
    if eps is None or bvps is None:
        return _nao(nome, "Sem dados suficientes")
    if eps <= 0 or bvps <= 0:
        return _nao(nome, "EPS ou valor contabilístico negativo")
    return ResultadoMetodo(nome, math.sqrt(22.5 * eps * bvps), True,
                           pressupostos={"eps": eps, "bvps": bvps})


def epv(e: Empresa) -> ResultadoMetodo:
    nome = "EPV"
    if e.e_financeira:
        return _nao(nome, "Não aplicável a bancos/seguradoras")
    if not e.acoes.valor:
        return _nao(nome, "Sem número de ações")
    ebit = e.anual["ebit"].ultimos(5) if "ebit" in e.anual else []
    caixa, divida = _ult(e, "caixa"), _ult(e, "divida_total")
    if not ebit or caixa is None or divida is None:
        return _nao(nome, "Sem dados suficientes")
    t, r = taxa_imposto(e), taxa_desconto(e)
    valor = (media(ebit) * (1 - t) / r + caixa - divida) / e.acoes.valor
    if valor <= 0:
        return _nao(nome, "Valor de EPV negativo")
    return ResultadoMetodo(nome, valor, True, pressupostos={"r": r, "taxa_imposto": t})


def _preco_fim_ano(e: Empresa, ano: int) -> float | None:
    p = e.precos.dropna()
    if p.empty:
        return None
    limite = pd.Timestamp(ano, 12, 31, tz=getattr(p.index, "tz", None))
    p = p[p.index <= limite]
    return float(p.iloc[-1]) if len(p) else None


def _acoes_ano(e: Empresa, ano: int) -> float | None:
    return _v(e, "acoes_media", ano) or e.acoes.valor


def _mediana_multiplos(multiplos: list[float]) -> tuple[float | None, str]:
    positivos = [m for m in multiplos if m > 0]
    if len(positivos) < carregar()["historico"]["anos_minimos"]:
        return None, "Histórico insuficiente"
    return statistics.median(positivos), ""


def pe_historico(e: Empresa) -> ResultadoMetodo:
    nome = "P/E histórico"
    eps_atual = _ult(e, "eps")
    mult = [p / eps for a in _anos(e, "eps")
            if (eps := _v(e, "eps", a)) and eps > 0 and (p := _preco_fim_ano(e, a))]
    mediana, motivo = _mediana_multiplos(mult)
    if mediana is None:
        return _nao(nome, motivo)
    if not eps_atual or eps_atual <= 0:
        return _nao(nome, "EPS atual negativo ou nulo")
    return ResultadoMetodo(nome, mediana * eps_atual, True,
                           pressupostos={"pe_mediano": mediana, "anos": len(mult)})


def ev_ebit_historico(e: Empresa) -> ResultadoMetodo:
    nome = "EV/EBIT histórico"
    if e.e_financeira:
        return _nao(nome, "Não aplicável a bancos/seguradoras")
    if not e.acoes.valor:
        return _nao(nome, "Sem número de ações")
    mult = []
    for a in _anos(e, "ebit"):
        ebit, d, c = _v(e, "ebit", a), _v(e, "divida_total", a), _v(e, "caixa", a)
        p, n = _preco_fim_ano(e, a), _acoes_ano(e, a)
        if ebit and ebit > 0 and d is not None and c is not None and p and n:
            mult.append((p * n + d - c) / ebit)
    mediana, motivo = _mediana_multiplos(mult)
    if mediana is None:
        return _nao(nome, motivo)
    ebit, d, c = _ult(e, "ebit"), _ult(e, "divida_total"), _ult(e, "caixa")
    if not ebit or ebit <= 0 or d is None or c is None:
        return _nao(nome, "EBIT atual negativo ou nulo")
    valor = (mediana * ebit - (d - c)) / e.acoes.valor
    if valor <= 0:
        return _nao(nome, "Valor implícito negativo")
    return ResultadoMetodo(nome, valor, True,
                           pressupostos={"ev_ebit_mediano": mediana, "anos": len(mult)})


def gordon(e: Empresa) -> ResultadoMetodo:
    nome = "Gordon (dividendos)"
    c = carregar()
    # troço final de anos consecutivos com dividendo positivo
    corrida: list[int] = []
    for a in sorted(a for a, v in e.dividendos.items() if v and v > 0):
        corrida = corrida + [a] if corrida and a == corrida[-1] + 1 else [a]
    if len(corrida) < c["historico"]["anos_minimos"]:
        return _nao(nome, "Dividendos insuficientes")
    dps = [e.dividendos[a] for a in corrida]
    if any(b < 0.75 * a for a, b in zip(dps, dps[1:])):
        return _nao(nome, "Dividendo cortado em mais de 25 %")
    r = taxa_desconto(e)
    taxa = cagr(Serie({a: e.dividendos[a] for a in corrida}, e.preco.fonte),
                c["historico"]["anos_pedidos"])[0]
    g = min(max(taxa or 0.0, 0.0), r - 0.01)
    return ResultadoMetodo(nome, dps[-1] * (1 + g) / (r - g), True,
                           pressupostos={"g": g, "r": r, "dps": dps[-1]})


def pb_bancos(e: Empresa) -> ResultadoMetodo:
    nome = "P/B (bancos)"
    if not e.e_financeira:
        return _nao(nome, "Só aplicável a bancos/seguradoras")
    bvps = _bvps(e)
    roes = [x for a in _anos(e, "lucro_liquido")[-5:] if (x := roe(e, a)) is not None]
    if bvps is None or not roes:
        return _nao(nome, "Sem dados suficientes")
    roe_medio, r = media(roes), taxa_desconto(e)
    if roe_medio <= 0 or bvps <= 0:
        return _nao(nome, "ROE médio ou valor contabilístico negativo")
    return ResultadoMetodo(nome, roe_medio / r * bvps, True,
                           pressupostos={"roe_medio": roe_medio, "r": r, "bvps": bvps})


def todos_os_metodos(e: Empresa) -> list[ResultadoMetodo]:
    return [f(e) for f in (dcf, owner_earnings, formula_graham, numero_graham, epv,
                           pe_historico, ev_ebit_historico, gordon, pb_bancos)]
