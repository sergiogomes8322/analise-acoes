from analise.indicadores import coef_variacao, divida_liquida_ebitda, janela, media
from analise.lentes._comum import cfg, criterio, lim, num, pct, positivo, resultado, ult
from analise.modelo import Empresa, ResultadoLente


def avaliar(e: Empresa) -> ResultadoLente:
    c = cfg("ackman")
    hist = janela(e.anual.get("receita"))
    receitas = hist.ultimos(len(hist.anos()))
    fcf, rec = ult(e, "fcf"), ult(e, "receita")
    margem = fcf / rec if fcf is not None and rec else None
    fcfs = e.anual["fcf"].ultimos(c["anos_fcf"]) if "fcf" in e.anual else []
    mfcf, cap = media(fcfs), e.capitalizacao.valor
    fy = mfcf / cap if mfcf is not None and cap else None

    criterios = [
        criterio("Estabilidade da receita", coef_variacao(receitas), lambda x: x <= c["cv_receita_max"],
                 lambda x: f"CV {num(x, 2)} (≤ {lim(c['cv_receita_max'])})", len(receitas)),
        criterio("Margem FCF", margem, lambda x: x >= c["margem_fcf_min"],
                 lambda x: f"Margem FCF {pct(x)} (≥ {pct(c['margem_fcf_min'], 0)})"),
        criterio("Dívida líquida / EBITDA", divida_liquida_ebitda(e),
                 lambda x: x <= c["divida_ebitda_max"],
                 lambda x: f"{num(x)}x (≤ {lim(c['divida_ebitda_max'])}x)"),
        criterio("FCF yield", fy, lambda x: x >= c["fcf_yield_min"],
                 lambda x: f"FCF yield {pct(x)} (≥ {pct(c['fcf_yield_min'], 0)})"),
    ]
    acoes = e.acoes.valor
    vj = positivo(mfcf / c["fcf_yield_min"] / acoes) if mfcf is not None and acoes else None
    return resultado("Bill Ackman", criterios, vj)
