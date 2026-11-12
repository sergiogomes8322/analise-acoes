import math
import os

import pandas as pd
import streamlit as st

from analise import servico
from analise.fontes import yahoo

NAO_ENCONTRADA = "Não encontrei esta ação. Experimenta o ticker (ex.: ASML.AS)."
INDISPONIVEL = "Yahoo Finance indisponível de momento. Tenta novamente mais tarde."
AVISO_LENTES = "As lentes são interpretações de princípios públicos destes investidores, não as suas opiniões."
RODAPE = "Informação educativa, não é aconselhamento financeiro."
SEM_VALOR_JUSTO = ("Druckenmiller", "Greenblatt")  # lentes que não estimam um preço
ICONES = {"ok": "✅", "falha": "❌", "nd": "➖"}


def formatar_numero(valor: float | None, moeda: str | None = None, casas: int = 2) -> str:
    if valor is None:
        return "N/D"
    s = f"{valor:,.{casas}f}".replace(",", " ").replace(".", ",")
    if moeda:
        s += " €" if moeda == "EUR" else f" {moeda}"
    return s


def formatar_pct(x: float | None, casas: int = 1) -> str:
    return "N/D" if x is None else formatar_numero(x * 100, casas=casas) + " %"


def fonte_md(fonte) -> str:
    ligacao = f" ([ligação]({fonte.url}))" if fonte.url else ""
    return f"Fonte: {fonte.nome}, {fonte.data}{ligacao}"


# As falhas (FonteIndisponivel) propagam-se: o cache_data não memoriza exceções.
@st.cache_data(ttl=43200)
def pesquisar(texto: str):
    return yahoo.pesquisar(texto)


@st.cache_data(ttl=43200)
def analisar(ticker: str, user_agent: str | None):
    return servico.analisar(ticker, user_agent)


def _user_agent() -> str | None:
    try:
        ua = st.secrets.get("SEC_USER_AGENT")
    except FileNotFoundError:  # sem secrets.toml
        ua = None
    return ua or os.environ.get("SEC_USER_AGENT")


def _pontuacao(p) -> str:
    if p.total is None:
        return "N/D"
    # trunca: 59,6 é "Fraca" (< 60); arredondar mostraria "60/100 · Fraca"
    return f"{math.floor(p.total)}/100 · {p.faixa}" + (" (dados insuficientes)" if p.dados_insuficientes else "")


def _pressupostos(d: dict) -> str:
    return "; ".join(f"{k}: {formatar_numero(v) if isinstance(v, (int, float)) else v}" for k, v in d.items())


def mostrar(f) -> None:
    e, vc, moeda = f.empresa, f.central, f.empresa.moeda
    taxa_eur = e.cambio_eur.valor if moeda != "EUR" else None

    st.subheader(" · ".join([e.nome, e.ticker, e.bolsa, moeda]))
    c1, c2, c3 = st.columns(3)
    c1.metric("Preço", formatar_numero(e.preco.valor, moeda))
    c2.metric("Pontuação", _pontuacao(f.pontuacao))
    c3.metric("Risco", f.risco)
    if moeda != "EUR":
        if taxa_eur is None:
            st.caption("Conversão para EUR indisponível")
        else:
            st.caption(f"≈ {formatar_numero(e.preco.valor * taxa_eur, 'EUR')}")
    st.caption(fonte_md(e.preco.fonte))

    if vc.central is None:
        st.markdown("**Valor intrínseco (central): N/D** (nenhum método aplicável)")
    else:
        eur = f" (≈ {formatar_numero(vc.central * taxa_eur, 'EUR')})" if taxa_eur is not None else ""
        st.markdown(f"**Valor intrínseco (central): {formatar_numero(vc.central, moeda)}**{eur} · "
                    f"intervalo {formatar_numero(vc.minimo, moeda)} – {formatar_numero(vc.maximo, moeda)} "
                    f"({vc.n_metodos} métodos)")
        sinal = "+" if vc.margem is not None and vc.margem > 0 else ""
        st.markdown(f"**Margem de segurança:** {sinal}{formatar_pct(vc.margem)}")
    st.divider()

    with st.expander("Sobre a empresa"):
        st.markdown(e.descricao or "Descrição: N/D")
        st.markdown(f"Setor: {e.setor or 'N/D'} · Indústria: {e.industria or 'N/D'} · País: {e.pais or 'N/D'}")
        st.markdown(f"Capitalização: {formatar_numero(e.capitalizacao.valor, moeda, casas=0)}")

    with st.expander("Crescimento ou valor"):
        tipo, razoes = f.classificacao
        st.markdown(f"**{tipo}**\n\n" + "\n".join(f"- {r}" for r in razoes))

    with st.expander("Riscos"):
        st.markdown(f"Risco: **{f.risco}**")
        st.markdown("\n".join(f"- ● {a.nome}: {a.valor} (limite {a.limite})" for a in f.alertas)
                    or "Sem alertas.")

    with st.expander("Valor intrínseco"):
        st.dataframe(pd.DataFrame([{
            "Método": m.nome,
            "Valor": formatar_numero(m.valor_por_acao, moeda),
            "Aplicável": "Sim" if m.aplicavel else "Não",
            "Motivo / pressupostos": m.motivo or _pressupostos(m.pressupostos),
        } for m in f.metodos]), hide_index=True)

    with st.expander("Lentes"):
        st.caption(AVISO_LENTES)
        for l in f.lentes:
            vj = ("sem valor justo" if any(n in l.investidor for n in SEM_VALOR_JUSTO)
                  else f"valor justo {formatar_numero(l.valor_justo, moeda)}")
            nota = f" · nota {l.nota:.0f}/100" if l.nota is not None else ""
            linhas = "\n".join(f"- {ICONES.get(c.estado, '')} {c.descricao}: {c.valor}" for c in l.criterios)
            st.markdown(f"**{l.investidor}** · {vj}{nota}\n\n{l.resumo}\n\n{linhas}")

    with st.expander("Pontuação"):
        p = f.pontuacao
        st.markdown(f"Pontuação: **{_pontuacao(p)}** · cobertura {formatar_pct(p.cobertura, 0)}")
        if p.componentes:
            st.dataframe(pd.DataFrame([{
                "Componente": c.nome, "Peso": formatar_pct(c.peso, 0),
                "Nota": formatar_numero(c.nota, casas=0),
                "Detalhe": "; ".join(f"{k}: {formatar_numero(v)}" for k, v in c.detalhe.items()),
            } for c in p.componentes]), hide_index=True)

    with st.expander("Fontes"):
        fontes = dict.fromkeys([*e.links, *(s.fonte for s in e.anual.values() if s.fonte.nome)])
        st.markdown("\n".join(f"- {fonte_md(x)}" for x in fontes))
        if e.cambio_eur.fonte.nome and taxa_eur is not None:
            st.caption(fonte_md(e.cambio_eur.fonte))
        for aviso in e.avisos:
            st.warning(aviso)


st.set_page_config(page_title="Análise de ações", layout="centered")
st.title("Análise de ações")
texto = st.text_input("Empresa ou ticker").strip()
if texto:
    try:
        achadas = pesquisar(texto)
        if not achadas:
            st.warning(NAO_ENCONTRADA)
        else:
            escolhida = achadas[0] if len(achadas) == 1 else st.radio(
                "Resultados", achadas, format_func=lambda c: f"{c.nome} · {c.ticker} · {c.bolsa}")
            ficha = analisar(escolhida.ticker, _user_agent())
            if ficha is None:
                st.warning(NAO_ENCONTRADA)
            else:
                mostrar(ficha)
    except yahoo.FonteIndisponivel:
        st.error(INDISPONIVEL)
st.caption(RODAPE)
