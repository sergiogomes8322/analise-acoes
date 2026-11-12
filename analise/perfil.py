from dataclasses import dataclass

from analise import indicadores as ind
from analise.config import carregar
from analise.modelo import Empresa

MOEDA = "Moeda ≠ EUR (risco cambial)"


def _n(x: float, casas: int = 2) -> str:
    return f"{x:,.{casas}f}".replace(",", " ").replace(".", ",")


def _pct(x: float) -> str:
    return _n(x * 100, 1) + " %"


def _pe(e: Empresa, preco: float) -> float | None:
    eps = e.anual["eps"].ultimo() if "eps" in e.anual else None
    return preco / eps if eps and eps > 0 else None


def _pb(e: Empresa, preco: float) -> float | None:
    cp = e.anual["capital_proprio"].ultimo() if "capital_proprio" in e.anual else None
    acoes = e.acoes.valor
    return preco / (cp / acoes) if cp and cp > 0 and acoes else None


def classificar(e: Empresa, preco: float) -> tuple[str, list[str]]:
    c = carregar()["perfil"]
    g = ind.cagr(e.anual["receita"], 3)[0] if "receita" in e.anual else None
    pe, pb = _pe(e, preco), _pb(e, preco)
    div = bool(e.dividendos) and e.dividendos[max(e.dividendos)] > 0

    cresc = []
    if g is not None and g >= c["crescimento_cagr"]:
        cresc.append(f"CAGR receitas 3 anos: {_pct(g)} (≥ {_pct(c['crescimento_cagr'])})")
    if pe is not None and pe > c["crescimento_pe"] and g is not None and g >= c["crescimento_pe_g"]:
        cresc.append(f"P/E {_n(pe, 1)} (> {c['crescimento_pe']}) com crescimento {_pct(g)} "
                     f"(≥ {_pct(c['crescimento_pe_g'])})")
    if cresc:
        return "Crescimento", cresc

    valor = []
    if pe is not None and pe < c["valor_pe"]:
        valor.append(f"P/E {_n(pe, 1)} (< {c['valor_pe']})")
    if pb is not None and pb < c["valor_pb"] and div:
        valor.append(f"P/B {_n(pb)} (< {_n(c['valor_pb'])}) com dividendo")
    if valor:
        return "Valor", valor
    return "Misto", ["Não cumpre os critérios de crescimento nem de valor"]


@dataclass
class Alerta:
    nome: str
    valor: str
    limite: str


def alertas(e: Empresa) -> list[Alerta]:
    c = carregar()["alertas"]
    # (nome, valor, limite, ativa_acima_do_limite, formato)
    regras = [
        ("Volatilidade 1 ano", ind.volatilidade_anual(e.precos), c["volatilidade"], True, _pct),
        ("Queda máxima 5 anos", ind.queda_maxima(e.precos), c["queda_maxima"], True, _pct),
        ("Beta", e.beta.valor, c["beta"], True, _n),
        ("Dívida líquida / EBITDA", ind.divida_liquida_ebitda(e), c["divida_liquida_ebitda"], True, _n),
        ("Diluição anual", ind.diluicao_anual(e), c["diluicao_anual"], True, _pct),
        ("Altman Z", ind.altman_z(e), c["altman_z"], False, _n),
        ("Cobertura de juros", ind.cobertura_juros(e), c["cobertura_juros"], False, _n),
    ]
    out = [Alerta(n, f(v), ("> " if acima else "< ") + f(lim))
           for n, v, lim, acima, f in regras
           if v is not None and (v > lim if acima else v < lim)]
    if e.moeda and e.moeda != "EUR":
        out.append(Alerta(MOEDA, e.moeda, "EUR"))
    return out


def etiqueta_risco(alertas: list[Alerta]) -> str:
    n = sum(a.nome != MOEDA for a in alertas)
    return "Baixo" if n <= 1 else "Médio" if n <= 3 else "Alto"
