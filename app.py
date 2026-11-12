import streamlit as st

from analise.fontes import yahoo

NAO_ENCONTRADA = "Não encontrei esta ação. Experimenta o ticker (ex.: ASML.AS)."
INDISPONIVEL = "Yahoo Finance indisponível de momento. Tenta novamente mais tarde."

st.set_page_config(page_title="Análise de ações")


# As falhas (FonteIndisponivel) propagam-se: o cache_data não memoriza exceções.
@st.cache_data(ttl=43200)
def pesquisar(texto: str):
    return yahoo.pesquisar(texto)


@st.cache_data(ttl=43200)
def carregar(ticker: str):
    return yahoo.carregar_empresa(ticker)


def fonte_md(fonte) -> str:
    ligacao = f" ([ligação]({fonte.url}))" if fonte.url else ""
    return f"Fonte: {fonte.nome}, {fonte.data}{ligacao}"


def mostrar(empresa) -> None:
    st.subheader(empresa.nome)
    st.metric("Preço", f"{empresa.preco.valor} {empresa.moeda}")
    st.caption(fonte_md(empresa.preco.fonte))
    receita = empresa.anual["receita"]
    anos = receita.anos()
    if anos:
        st.write(f"Anos de receita: {len(anos)} ({anos[0]}–{anos[-1]})")
    else:
        st.write("Receita: N/D (sem balanços disponíveis)")
    st.caption(fonte_md(receita.fonte))


st.title("Análise de ações")
texto = st.text_input("Empresa ou ticker").strip()
if texto:
    try:
        achadas = pesquisar(texto)
        if not achadas:
            st.warning(NAO_ENCONTRADA)
        else:
            escolhida = st.selectbox("Resultados", achadas,
                                     format_func=lambda c: f"{c.nome} ({c.ticker}, {c.bolsa})")
            empresa = carregar(escolhida.ticker)
            if empresa is None:
                st.warning(NAO_ENCONTRADA)
            else:
                mostrar(empresa)
    except yahoo.FonteIndisponivel:
        st.error(INDISPONIVEL)
