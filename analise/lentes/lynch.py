from analise.indicadores import cagr, historico_insuficiente, janela
from analise.lentes._comum import cfg, criterio, lim, num, pct, positivo, resultado, ult
from analise.modelo import Empresa, ResultadoLente


def avaliar(e: Empresa) -> ResultadoLente:
    c = cfg("lynch")
    eps, preco = ult(e, "eps"), e.preco.valor
    hist = janela(e.anual.get("eps"))
    n = len(hist.anos())
    g = None if historico_insuficiente(n) else cagr(hist, n)[0]  # fracao
    pe = None if eps is None or preco is None else (preco / eps if eps > 0 else float("inf"))
    peg = None if pe is None or g is None else (pe / (g * 100) if g > 0 else float("inf"))
    divida, cp = ult(e, "divida_total"), ult(e, "capital_proprio")
    dc = None if divida is None or cp is None else (divida / cp if cp > 0 else float("inf"))

    criterios = [
        criterio("PEG", peg, lambda x: x <= c["peg_max"],
                 lambda x: f"PEG {num(x, 2)} (≤ {lim(c['peg_max'])})", n, "CAGR de "),
        criterio("Dívida total / capital próprio", dc, lambda x: x <= c["divida_capital_max"],
                 lambda x: f"{num(x, 2)} (≤ {lim(c['divida_capital_max'])})"),
        criterio("Crescimento do EPS", g, lambda x: c["g_min"] <= x <= c["g_max"],
                 lambda x: f"EPS {pct(x)} ({pct(c['g_min'], 0)} a {pct(c['g_max'], 0)})", n, "CAGR de "),
    ]
    vj = None if eps is None or g is None else \
        positivo(eps * min(g * 100, c["g_max"] * 100))
    return resultado("Peter Lynch", criterios, vj)
