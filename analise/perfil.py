from dataclasses import dataclass

from analise import indicadores as ind
from analise.config import carregar
from analise.modelo import Empresa

MOEDA = "Moeda ≠ EUR (risco cambial)"
COBERTURA = "Cobertura de juros"
CONCENTRACAO = "Lucros concentrados num ano"
INFORMATIVOS = {MOEDA, COBERTURA, CONCENTRACAO}  # aparecem na lista mas não contam para a etiqueta


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
class Etiqueta:
    grupo: str
    nome: str
    explicacao: str
    razoes: list[str]


EXPLICACOES = {
    "Crescimento": "As receitas crescem depressa ou o mercado paga caro por crescimento futuro. Mais potencial, mais oscilação.",
    "Valor": "Está barata face aos lucros ou aos ativos. O retorno depende de o mercado reconhecer esse valor.",
    "Misto": "Não é claramente de crescimento nem de valor.",
    "Grande empresa": "Large cap (≥ 10 mil M€). Mais estável e com mais informação disponível.",
    "Média empresa": "Mid cap (2–10 mil M€). Equilíbrio entre estabilidade e potencial de crescimento.",
    "Pequena empresa": "Small cap (< 2 mil M€). Mais potencial, mas mais volátil e menos líquida.",
    "Blue chip": "Empresa grande e sólida: lucro todos os anos, dividendos regulares e dívida controlada. Costuma oscilar menos.",
    "Penny stock": "Ação muito barata por unidade (< 5 €). Normalmente muito volátil e especulativa; cuidado redobrado.",
    "Small cap especulativa": "Pequena e a perder dinheiro ou a queimar caixa. Risco elevado de perda.",
    "Recuperação": "Lynch: voltou ao lucro depois de prejuízo. Pode subir muito se a recuperação continuar.",
    "Rica em ativos": "Lynch: vale em bolsa menos do que o capital próprio (P/B < 1). Os ativos podem valer mais do que o preço.",
    "Cíclica (Lynch)": "Lynch: os lucros sobem e descem com a economia. O momento de compra conta muito.",
    "Crescimento lento": "Lynch: receitas a crescer pouco (< 5 %/ano). Interessa sobretudo pelos dividendos.",
    "Crescimento estável": "Lynch (\"stalwart\"): crescimento moderado e previsível (5–15 %/ano). Protege em crises.",
    "Crescimento rápido": "Lynch: receitas a crescer ≥ 15 %/ano. Grande potencial, mas o preço costuma já ser exigente.",
    "Defensiva": "Setor que vende o essencial (consumo básico, saúde, energia elétrica). Sofre menos em recessões.",
    "Cíclica": "Setor ligado ao ciclo económico (energia, materiais, indústria, consumo não essencial).",
    "Sensível ao juro": "Setor financeiro ou imobiliário: os resultados dependem muito das taxas de juro.",
    "Rendimento (dividendos)": "Dividend yield ≥ 3 %: paga uma parte relevante do preço em dividendos todos os anos.",
    "Paga dividendo": "Paga dividendo, mas abaixo de 3 % do preço.",
    "Não paga dividendo": "Não pagou dividendos no período disponível; o retorno vem só da valorização.",
}


def etiquetas(e: Empresa, preco: float | None) -> list[Etiqueta]:
    """Perfil da empresa: várias etiquetas, cada uma com explicação e os números que a justificam."""
    c = carregar()["perfil"]
    pedidos = carregar()["historico"]["anos_pedidos"]
    out: list[Etiqueta] = []

    def add(grupo: str, nome: str, *razoes: str) -> None:
        out.append(Etiqueta(grupo, nome, EXPLICACOES[nome], list(razoes)))

    estilo, razoes = classificar(e, preco) if preco else ("Misto", [])
    add("Estilo", estilo, *razoes)

    fx = e.cambio_eur.valor
    cap_eur = e.capitalizacao.valor * fx if e.capitalizacao.valor and fx else None
    if cap_eur is not None:
        nome = ("Grande empresa" if cap_eur >= c["grande_eur"] else
                "Média empresa" if cap_eur >= c["pequena_eur"] else "Pequena empresa")
        add("Dimensão", nome, f"Capitalização {_n(cap_eur / 1e6, 0)} M€")

    lucros = ind.janela(e.anual.get("lucro_liquido")).ultimos(pedidos)
    divs = [e.dividendos[a] for a in sorted(e.dividendos)][-pedidos:]
    nd = ind.divida_liquida_ebitda(e)
    if (cap_eur is not None and cap_eur >= c["grande_eur"] and len(lucros) >= pedidos and min(lucros) > 0
            and len(divs) >= pedidos and min(divs) > 0 and nd is not None and nd <= c["blue_chip_divida_ebitda"]):
        add("Blue chip", "Blue chip", f"Lucro positivo {len(lucros)}/{len(lucros)} anos",
            f"Dividendos {len(divs)}/{len(divs)} anos", f"Dívida líquida/EBITDA {_n(nd)} (≤ {_n(c['blue_chip_divida_ebitda'])})")

    if preco and fx and preco * fx < c["penny_eur"]:
        add("Especulação", "Penny stock", f"Preço {_n(preco * fx)} € (< {_n(c['penny_eur'])} €)")
    fcf = e.anual["fcf"].ultimo() if "fcf" in e.anual else None
    a_perder = (lucros and lucros[-1] <= 0) or (fcf is not None and fcf < 0)
    if cap_eur is not None and cap_eur < c["pequena_eur"] and a_perder:
        add("Especulação", "Small cap especulativa",
            "Prejuízo no último ano" if lucros and lucros[-1] <= 0 else "FCF negativo no último ano")

    pb = _pb(e, preco) if preco else None
    g = ind.cagr(ind.janela(e.anual.get("receita")), pedidos)[0]
    if len(lucros) >= 2 and lucros[-2] < 0 < lucros[-1]:
        add("Categoria Lynch", "Recuperação", "Prejuízo no penúltimo ano, lucro no último")
    elif pb is not None and pb < c["ativos_pb"]:
        add("Categoria Lynch", "Rica em ativos", f"P/B {_n(pb)} (< {_n(c['ativos_pb'])})")
    elif e.setor in c["setores_ciclicos"]:
        add("Categoria Lynch", "Cíclica (Lynch)", f"Setor: {e.setor}")
    elif g is not None:
        nome = ("Crescimento lento" if g < c["lynch_lento"] else
                "Crescimento estável" if g < c["lynch_rapido"] else "Crescimento rápido")
        add("Categoria Lynch", nome, f"Crescimento das receitas {_pct(g)}/ano")

    for lista, nome in (("setores_defensivos", "Defensiva"), ("setores_ciclicos", "Cíclica"),
                        ("setores_juro", "Sensível ao juro")):
        if e.setor in c[lista]:
            add("Setor", nome, f"Setor: {e.setor}")

    if divs and divs[-1] > 0 and preco:
        y = divs[-1] / preco
        add("Dividendos", "Rendimento (dividendos)" if y >= c["rendimento_min"] else "Paga dividendo",
            f"Dividend yield {_pct(y)}")
    else:
        add("Dividendos", "Não paga dividendo")
    return out


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
        ("FCF negativo", e.anual["fcf"].ultimo() if "fcf" in e.anual else None,
         c["fcf_negativo"], False, _n),
        (CONCENTRACAO, ind.concentracao_lucros(e), c["concentracao_lucros"], True, _pct),
    ]
    out = [Alerta(n, f(v), ("> " if acima else "< ") + f(lim))
           for n, v, lim, acima, f in regras
           if v is not None and (v > lim if acima else v < lim)]
    if e.moeda and e.moeda != "EUR":
        out.append(Alerta(MOEDA, e.moeda, "EUR"))
    return out


def etiqueta_risco(alertas: list[Alerta]) -> str:
    n = sum(a.nome not in INFORMATIVOS for a in alertas)
    return "Baixo" if n <= 1 else "Médio" if n <= 3 else "Alto"
