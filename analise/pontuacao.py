from analise import indicadores as ind
from analise.config import carregar
from analise.modelo import Componente, Empresa, Pontuacao
from analise.valor.central import ValorCentral


def agregar(notas: dict[str, float | None]) -> Pontuacao:
    cfg = carregar()["pontuacao"]
    pesos, faixas = cfg["pesos"], cfg["faixas"]
    comps = [Componente(n, p, notas.get(n)) for n, p in pesos.items()]
    com = [c for c in comps if c.nota is not None]
    cobertura = round(sum(c.peso for c in com), 9)  # evita 77.999... por soma de floats
    total = round(sum(c.peso * c.nota for c in com) / cobertura, 9) if com else None
    if total is None:
        faixa = "Sem dados"
    elif total >= faixas["boa"] and cobertura >= faixas["cobertura_minima"]:
        faixa = "Boa"
    else:
        faixa = "Neutra" if total >= faixas["neutra"] else "Fraca"
    return Pontuacao(total, cobertura, faixa, cobertura < faixas["cobertura_minima"], comps)


def _sub(e: Empresa, vc: ValorCentral) -> dict[str, dict[str, float | None]]:
    anual = e.anual
    anos = anual["ebit"].anos() if "ebit" in anual else []
    roic = ind.media([r for a in anos if (r := ind.roic(e, a)) is not None])
    margens = [m for a in anos if (m := ind.margem_operacional(e, a)) is not None]
    receita = anual.get("receita")
    return {
        "valorizacao": {"margem_seguranca": vc.margem},
        "qualidade": {
            "roic": roic,
            "cv_margem_operacional": ind.coef_variacao(margens),
            "anos_receita_a_crescer": ind.fracao_anos_a_crescer(receita) if receita is not None else None,
        },
        "solidez": {
            "divida_liquida_ebitda": ind.divida_liquida_ebitda(e),
            "cobertura_juros": ind.cobertura_juros(e),
            "altman_z": ind.altman_z(e),
            "piotroski_f": ind.piotroski_f(e),
        },
        "risco_mercado": {
            "beta": e.beta.valor,
            "volatilidade": ind.volatilidade_anual(e.precos),
            "queda_maxima": ind.queda_maxima(e.precos),
        },
        "tendencia": {
            "preco_vs_mm200": ind.preco_vs_mm200(e.precos),
            "momento_12_1": ind.momento(e.precos, 12, 1),
        },
    }


def calcular_pontuacao(e: Empresa, vc: ValorCentral) -> Pontuacao:
    limites = carregar()["pontuacao"]["limites"]
    sub = _sub(e, vc)
    notas = {}
    for comp, valores in sub.items():
        ns = [n for k, v in valores.items() if (n := ind.escala(v, *limites[k])) is not None]
        notas[comp] = ind.media(ns)
    p = agregar(notas)
    for c in p.componentes:
        c.detalhe = sub[c.nome]
    return p
