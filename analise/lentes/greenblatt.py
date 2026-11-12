from analise.indicadores import escala, media
from analise.lentes._comum import cfg, criterio, pct, resultado, ult
from analise.modelo import Empresa, ResultadoLente


def avaliar(e: Empresa) -> ResultadoLente:
    c = cfg("greenblatt")
    ebit, cap = ult(e, "ebit"), e.capitalizacao.valor
    divida, caixa = ult(e, "divida_total"), ult(e, "caixa")
    ev = None if None in (cap, divida, caixa) else cap + divida - caixa
    ey = ebit / ev if ebit is not None and ev and ev > 0 else None
    ac, pc, imob = ult(e, "ativo_corrente"), ult(e, "passivo_corrente"), ult(e, "imobilizado")
    capital = None if None in (ac, pc, imob) else ac - pc + imob
    roc = ebit / capital if ebit is not None and capital and capital > 0 else None

    criterios = [
        criterio("Earnings yield (EBIT/EV)", ey, lambda x: x >= c["ey_min"],
                 lambda x: f"EY {pct(x)} (≥ {pct(c['ey_min'], 0)})"),
        criterio("Retorno sobre o capital", roc, lambda x: x >= c["roc_min"],
                 lambda x: f"ROC {pct(x)} (≥ {pct(c['roc_min'], 0)})"),
    ]
    notas = [escala(ey, *c["ey_escala"]), escala(roc, *c["roc_escala"])]
    nota = media(notas) if None not in notas else None
    resumo = "Sem dados suficientes" if nota is None else f"Nota {nota:.0f}/100".replace(".", ",")
    return resultado("Joel Greenblatt", criterios, None, resumo, nota)
