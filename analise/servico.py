from dataclasses import dataclass

from analise import lentes, perfil
from analise.fontes import esef, sec, yahoo
from analise.modelo import Empresa, Pontuacao, ResultadoLente, ResultadoMetodo
from analise.pontuacao import calcular_pontuacao
from analise.valor.central import ValorCentral, valor_central
from analise.valor.outros import ev_ebit_historico, pe_historico, todos_os_metodos


@dataclass
class Ficha:
    empresa: Empresa
    metodos: list[ResultadoMetodo]
    central: ValorCentral
    lentes: list[ResultadoLente]
    pontuacao: Pontuacao
    perfil: list[perfil.Etiqueta]
    alertas: list[perfil.Alerta]
    risco: str


def analisar(ticker: str, user_agent: str | None) -> Ficha | None:
    """Ficha completa de `ticker`, ou None se não existir. FonteIndisponivel propaga-se."""
    e = yahoo.carregar_empresa(ticker)
    if e is None:
        return None
    e = esef.enriquecer(sec.enriquecer(e, user_agent))
    metodos = todos_os_metodos(e)
    central = valor_central(metodos, e.preco.valor)
    # A pontuação mede o preço face aos múltiplos habituais da própria ação (escolha do utilizador),
    # não face ao valor central, que os métodos clássicos puxam para baixo nas empresas de qualidade.
    historico = valor_central([pe_historico(e), ev_ebit_historico(e)], e.preco.valor)
    alertas = perfil.alertas(e)
    return Ficha(e, metodos, central, lentes.todas(e), calcular_pontuacao(e, historico),
                 perfil.etiquetas(e, e.preco.valor), alertas, perfil.etiqueta_risco(alertas))
