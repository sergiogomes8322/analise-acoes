from analise.indicadores import media, momento, preco_vs_mm200
from analise.lentes._comum import cfg, criterio, pct, resultado
from analise.modelo import Empresa, ResultadoLente


def avaliar(e: Empresa) -> ResultadoLente:
    c = cfg("druckenmiller")
    n = c["anos_eps_anteriores"]
    eps = e.anual["eps"].ultimos(n + 1) if "eps" in e.anual else []
    eps_ok = (eps[-1], media(eps[:-1])) if len(eps) == n + 1 else None

    def mom(meses: int):
        return criterio(f"Momento {meses} meses", momento(e.precos, meses),
                        lambda x: x > c["momento_min"],
                        lambda x: f"{pct(x)} (> {pct(c['momento_min'], 0)})")

    criterios = [
        criterio("Preço acima da MM200", preco_vs_mm200(e.precos),
                 lambda x: x > c["mm200_min"],
                 lambda x: f"{pct(x)} vs MM200 (> {pct(c['mm200_min'], 0)})"),
        mom(c["meses_curto"]),
        mom(c["meses_longo"]),
        criterio("EPS acima da média anterior", eps_ok, lambda x: x[0] > x[1],
                 lambda x: f"EPS {x[0]:.2f} vs média {x[1]:.2f}".replace(".", ",")),
    ]
    ok = sum(k.estado == "ok" for k in criterios)
    resumo = ("Sinal favorável" if ok >= c["sinais_favoravel"] else
              "Sinal neutro" if ok >= c["sinais_neutro"] else "Sinal desfavorável")
    return resultado("Stanley Druckenmiller", criterios, None, resumo)
