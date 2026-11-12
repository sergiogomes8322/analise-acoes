import streamlit as st

from analise.fontes import yahoo

NAO_ENCONTRADA = "Não encontrei esta ação. Experimenta o ticker (ex.: ASML.AS)."

st.set_page_config(page_title="Análise de ações")


@st.cache_data(ttl=43200)
def pesquisar(texto: str):
    return yahoo.pesquisar(texto)


@st.cache_data(ttl=43200)
def carregar(ticker: str):
    return yahoo.carregar_empresa(ticker)


st.title("Análise de ações")
texto = st.text_input("Empresa ou ticker").strip()
if texto:
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
            st.subheader(empresa.nome)
            st.metric("Preço", f"{empresa.preco.valor} {empresa.moeda}")
            st.write(f"Anos de receita: {len(empresa.anual['receita'].anos())}")
