import math
from typing import Callable

from analise.config import carregar
from analise.indicadores import _ultimo_ano, _v, historico_insuficiente, nota_anos
from analise.modelo import Criterio, Empresa, ResultadoLente


def cfg(nome: str) -> dict:
    return carregar()["lentes"][nome]


def ult(e: Empresa, campo: str) -> float | None:
    ano = _ultimo_ano(e, campo)
    return _v(e, campo, ano) if ano is not None else None


def num(x: float, casas: int = 1) -> str:
    return "∞" if math.isinf(x) else f"{x:.{casas}f}".replace(".", ",")


def pct(x: float, casas: int = 1) -> str:
    return num(x * 100, casas) + " %"


def lim(x: float) -> str:
    """Limite sem zeros a mais: 15, 22,5."""
    return f"{x:g}".replace(".", ",")


def criterio(descricao: str, x, passa: Callable[[object], bool],
             texto: Callable[[object], str], anos: int | None = None, prefixo: str = "") -> Criterio:
    """`x` None = sem dados; `texto(x)` mostra o número e o limite.

    `anos`: n.º de anos usados num critério plurianual (spec §7): abaixo do mínimo fica N/D;
    abaixo dos pedidos o valor diz quantos se usaram (ex. "média de 4 anos (pedidos 5)").
    """
    if anos is not None and (motivo := historico_insuficiente(anos)):
        return Criterio(descricao, "nd", "N/D" if anos == 0 else motivo)
    if x is None:
        return Criterio(descricao, "nd", "N/D")
    nota = nota_anos(anos, prefixo) if anos is not None else ""
    return Criterio(descricao, "ok" if passa(x) else "falha", texto(x) + (f" · {nota}" if nota else ""))


def resultado(investidor: str, criterios: list[Criterio], valor_justo: float | None,
              resumo: str | None = None, nota: float | None = None) -> ResultadoLente:
    ok = sum(c.estado == "ok" for c in criterios)
    return ResultadoLente(investidor, criterios, valor_justo,
                          resumo or f"{ok}/{len(criterios)} critérios cumpridos", nota)


def positivo(x: float | None) -> float | None:
    """Valor justo nunca nulo/negativo: sem base fica None."""
    return x if x is not None and x > 0 else None
