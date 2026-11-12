from analise.indicadores import _anos
from analise.lentes._comum import cfg, criterio, lim, num, positivo, resultado, ult
from analise.modelo import Empresa, ResultadoLente
from analise.valor.outros import _bvps, numero_graham


def avaliar(e: Empresa) -> ResultadoLente:
    c = cfg("graham")
    cap, fx = e.capitalizacao.valor, e.cambio_eur.valor
    cap_eur = cap * fx if cap is not None and fx is not None else None
    ac, pc = ult(e, "ativo_corrente"), ult(e, "passivo_corrente")
    cr = ac / pc if ac is not None and pc else None
    lucros = e.anual["lucro_liquido"].ultimos(99) if "lucro_liquido" in e.anual else []
    anos = _anos(e, "lucro_liquido")
    divs = None if not anos or not e.dividendos else all(e.dividendos.get(a, 0) > 0 for a in anos)
    eps, bvps, preco = ult(e, "eps"), _bvps(e), e.preco.valor
    pe = None if eps is None or preco is None else (preco / eps if eps > 0 else float("inf"))
    pb = None if bvps is None or preco is None else (preco / bvps if bvps > 0 else float("inf"))
    pepb = None if pe is None or pb is None else pe * pb

    criterios = [
        criterio("Capitalização", cap_eur, lambda x: x >= c["capitalizacao_min_eur"],
                 lambda x: f"{num(x / 1e6, 0)} M EUR (≥ {num(c['capitalizacao_min_eur'] / 1e6, 0)} M EUR)"),
        criterio("Current ratio", cr, lambda x: x >= c["current_ratio_min"],
                 lambda x: f"Current ratio {num(x)} (≥ {lim(c['current_ratio_min'])})"),
        criterio("Lucro positivo todos os anos", min(lucros) if lucros else None,
                 lambda x: x > 0, lambda x: f"Lucro mínimo {num(x / 1e6, 0)} M (> 0)"),
        criterio("Dividendos todos os anos", divs, lambda x: x,
                 lambda x: "Dividendos em todos os anos" if x else "Anos sem dividendos"),
        criterio("P/E", pe, lambda x: x <= c["pe_max"],
                 lambda x: f"P/E {num(x)} (≤ {lim(c['pe_max'])})"),
        criterio("P/E × P/B", pepb, lambda x: x <= c["pe_pb_max"],
                 lambda x: f"P/E×P/B {num(x)} (≤ {lim(c['pe_pb_max'])})"),
    ]
    return resultado("Benjamin Graham", criterios, positivo(numero_graham(e).valor_por_acao))
