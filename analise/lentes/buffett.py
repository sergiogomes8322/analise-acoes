from analise.indicadores import _anos, coef_variacao, margem_operacional, media, roe
from analise.lentes._comum import cfg, criterio, lim, num, pct, positivo, resultado, ult
from analise.modelo import Empresa, ResultadoLente
from analise.valor.dcf import owner_earnings


def avaliar(e: Empresa) -> ResultadoLente:
    c = cfg("buffett")
    roes = [r for a in _anos(e, "lucro_liquido") if (r := roe(e, a)) is not None]
    m, cv = media(roes), coef_variacao(roes)
    lucro, divida = ult(e, "lucro_liquido"), ult(e, "divida_total")
    razao = None if lucro is None or divida is None else \
        (divida / lucro if lucro > 0 else float("inf"))
    cvm = coef_variacao([x for a in _anos(e, "ebit") if (x := margem_operacional(e, a)) is not None])
    lucros = e.anual["lucro_liquido"].ultimos(99) if "lucro_liquido" in e.anual else []

    criterios = [
        criterio("ROE médio e estabilidade", None if m is None or cv is None else (m, cv),
                 lambda x: x[0] >= c["roe_min"] and x[1] <= c["cv_roe_max"],
                 lambda x: f"ROE {pct(x[0])} (≥ {pct(c['roe_min'], 0)}), "
                           f"CV {num(x[1], 2)} (≤ {lim(c['cv_roe_max'])})"),
        criterio("Dívida total / lucro", razao, lambda x: x <= c["divida_lucro_max"],
                 lambda x: f"{num(x)}x (≤ {lim(c['divida_lucro_max'])}x)"),
        criterio("Estabilidade da margem operacional", cvm, lambda x: x <= c["cv_margem_max"],
                 lambda x: f"CV {num(x, 2)} (≤ {lim(c['cv_margem_max'])})"),
        criterio("Lucro positivo todos os anos", min(lucros) if lucros else None,
                 lambda x: x > 0, lambda x: f"Lucro mínimo {num(x / 1e6, 0)} M (> 0)"),
    ]
    vpa = owner_earnings(e).valor_por_acao
    vj = positivo(vpa * (1 - c["margem_seguranca"]) if vpa else None)
    return resultado("Warren Buffett", criterios, vj)
