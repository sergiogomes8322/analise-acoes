import math
import os

import pandas as pd
import streamlit as st

from analise import servico
from analise.fontes import yahoo

NAO_ENCONTRADA = "Não encontrei esta ação. Experimenta o ticker (ex.: ASML.AS)."
INDISPONIVEL = "Yahoo Finance indisponível de momento. Tenta novamente mais tarde."
LIMITADA = "Análise limitada: banco/seguradora — métodos baseados em FCF não se aplicam."
ERRO_INESPERADO = "Ocorreu um erro inesperado ao analisar esta ação."
AVISO_LENTES = "As lentes são interpretações de princípios públicos destes investidores, não as suas opiniões."
RODAPE = "Informação educativa, não é aconselhamento financeiro."
SEM_VALOR_JUSTO = ("Druckenmiller", "Greenblatt")  # lentes que não estimam um preço
ICONES = {"ok": "✅", "falha": "❌", "nd": "➖"}
NB = " "  # espaço não separável: "1 234,50 €" não parte a meio no telemóvel


def formatar_numero(valor: float | None, moeda: str | None = None, casas: int = 2) -> str:
    if valor is None:
        return "N/D"
    if round(valor, casas) == 0:
        valor = 0.0  # evita "-0,00"
    s = f"{valor:,.{casas}f}".replace(",", NB).replace(".", ",")
    if moeda:
        s += NB + ("€" if moeda == "EUR" else moeda)
    return s


def formatar_pct(x: float | None, casas: int = 1) -> str:
    return "N/D" if x is None else formatar_numero(x * 100, casas=casas) + NB + "%"


def fonte_md(fonte) -> str:
    ligacao = f" ([ligação]({fonte.url}))" if fonte.url else ""
    return f"Fonte: {fonte.nome}, {fonte.data}{ligacao}"


# As falhas (FonteIndisponivel) propagam-se: o cache_data não memoriza exceções.
@st.cache_data(ttl=43200)
def pesquisar(texto: str):
    return yahoo.pesquisar(texto)


class _NaoEncontrada(Exception):
    """Sai de _analisar como exceção para "não encontrada" não ficar 12 h em cache."""


@st.cache_data(ttl=43200)
def _analisar(ticker: str, user_agent: str | None):
    ficha = servico.analisar(ticker, user_agent)
    if ficha is None:
        raise _NaoEncontrada
    return ficha


def analisar(ticker: str, user_agent: str | None):
    try:
        return _analisar(ticker, user_agent)
    except _NaoEncontrada:
        return None


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


def _valor(v) -> str:
    if isinstance(v, bool):  # bool é int: tem de vir antes do ramo numérico
        return "Sim" if v else "Não"
    return formatar_numero(v) if v is None or isinstance(v, (int, float)) else str(v)


def _pressupostos(d: dict) -> str:
    return "; ".join(f"{k}: {_valor(v)}" for k, v in d.items())


def mostrar(f) -> None:
    e, vc, moeda = f.empresa, f.central, f.empresa.moeda
    taxa_eur = e.cambio_eur.valor if moeda != "EUR" else None

    st.subheader(" · ".join([e.nome, e.ticker, e.bolsa, moeda]))
    st.markdown(f"**Pontuação: {_pontuacao(f.pontuacao)}**")  # linha inteira: num metric estreito cortava
    c1, c2 = st.columns(2)
    c1.metric("Preço", formatar_numero(e.preco.valor, moeda))
    c2.metric("Risco", f.risco)
    if moeda != "EUR":
        if taxa_eur is None:
            st.caption("Conversão para EUR indisponível")
        else:
            st.caption(f"≈ {formatar_numero(e.preco.valor * taxa_eur, 'EUR')}")
    st.caption(fonte_md(e.preco.fonte))
    if e.e_financeira:
        st.caption(LIMITADA)

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

    with st.expander("Perfil da empresa"):
        st.markdown(" · ".join(f"**{t.nome}**" for t in f.perfil))
        for t in f.perfil:
            st.markdown(f"**{t.nome}** — {t.explicacao}"
                        + (f"\n\n<small>{'; '.join(t.razoes)}</small>" if t.razoes else ""),
                        unsafe_allow_html=True)

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
                "Detalhe": "; ".join(f"{k}: {formatar_numero(v, casas=0 if isinstance(v, int) else 2)}"
                                     for k, v in c.detalhe.items()),
            } for c in p.componentes]), hide_index=True)

    with st.expander("Fontes"):
        fontes = dict.fromkeys(x for x in [*e.links, *(s.fonte for s in e.anual.values()),
                                           e.taxa_sem_risco.fonte, e.cambio_eur.fonte] if x.nome)
        st.markdown("\n".join(f"- {fonte_md(x)}" for x in fontes))
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
    except Exception:  # dados inesperados de uma fonte: mensagem em vez de traceback
        st.error(ERRO_INESPERADO)
st.caption(RODAPE)
