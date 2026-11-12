from analise.config import carregar
from analise.indicadores import _v, _ultimo_ano, cagr, historico_insuficiente, janela, media, nota_anos
from analise.modelo import Empresa, ResultadoMetodo


def taxa_desconto(e: Empresa) -> float:
    c = carregar()
    rf = e.taxa_sem_risco.valor
    if rf is None:
        defeitos = c["sem_risco_defeito"]
        rf = defeitos.get(e.moeda, defeitos["OUTRA"])
    beta = e.beta.valor if e.beta.valor is not None else c["dcf"]["beta_defeito"]
    return max(rf + c["dcf"]["premio_mercado"] * beta, c["dcf"]["desconto_minimo"])


def valor_presente(base: float, g0: float, gT: float, r: float, anos: int) -> float:
    vp, fluxo = 0.0, base
    for t in range(1, anos + 1):
        g = g0 + (gT - g0) * (t - 1) / (anos - 1) if anos > 1 else gT
        fluxo *= 1 + g
        vp += fluxo / (1 + r) ** t
    return vp + fluxo * (1 + gT) / (r - gT) / (1 + r) ** anos


def _g0(e: Empresa, alternativa: str) -> tuple[float, int]:
    """CAGR das receitas (ou de `alternativa`) nos últimos anos pedidos, limitado; e n.º de anos."""
    s = janela(e.anual.get("receita"))
    if not s.anos():
        s = janela(e.anual.get(alternativa))
    taxa = cagr(s, len(s.anos()))[0]
    return min(max(taxa or 0.0, 0.0), carregar()["dcf"]["crescimento_max"]), len(s.anos())


def _avaliar(e: Empresa, nome: str, base: float | None, motivo_neg: str,
             alternativa: str, anos_historico: int) -> ResultadoMetodo:
    if e.e_financeira:
        return ResultadoMetodo(nome, None, False, "Não aplicável a bancos/seguradoras")
    if not e.acoes.valor:
        return ResultadoMetodo(nome, None, False, "Sem número de ações")
    if base is None:
        return ResultadoMetodo(nome, None, False, "Sem dados suficientes")
    g0, n_g0 = _g0(e, alternativa)
    if motivo := historico_insuficiente(min(anos_historico, n_g0)):
        return ResultadoMetodo(nome, None, False, motivo)
    if base <= 0:
        return ResultadoMetodo(nome, None, False, motivo_neg)
    d = carregar()["dcf"]
    gT, r = d["crescimento_terminal"], taxa_desconto(e)
    vp = valor_presente(base, g0, gT, r, d["anos"])
    p = {"g0": g0, "gT": gT, "r": r, "base": base, "anos_historico": anos_historico}
    if nota := nota_anos(n_g0, "CAGR de "):
        p["histórico"] = nota
    return ResultadoMetodo(nome, vp / e.acoes.valor, True, pressupostos=p)


def dcf(e: Empresa) -> ResultadoMetodo:
    s = e.anual.get("fcf")
    valores = s.ultimos(3) if s else []
    return _avaliar(e, "DCF", media(valores), "FCF médio negativo", "fcf", len(valores))


def owner_earnings(e: Empresa) -> ResultadoMetodo:
    capex = e.anual["capex"].ultimos(3) if "capex" in e.anual else []
    ano = _ultimo_ano(e, "lucro_liquido")
    ll = _v(e, "lucro_liquido", ano) if ano else None
    am = _v(e, "amortizacoes", _ultimo_ano(e, "amortizacoes") or 0)
    # capex vem negativo em alguns fornecedores; abs normaliza
    base = None if ll is None or am is None or not capex else \
        ll + am - media([abs(c) for c in capex])
    return _avaliar(e, "Owner earnings", base, "Owner earnings negativos",
                    "lucro_liquido", len(capex))
