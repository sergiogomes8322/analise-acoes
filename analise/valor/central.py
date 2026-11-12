import statistics
from dataclasses import dataclass

from analise.modelo import ResultadoMetodo


@dataclass
class ValorCentral:
    central: float | None
    minimo: float | None
    maximo: float | None
    margem: float | None
    n_metodos: int


def valor_central(metodos: list[ResultadoMetodo], preco: float) -> ValorCentral:
    v = [m.valor_por_acao for m in metodos if m.aplicavel and m.valor_por_acao is not None]
    if not v:
        return ValorCentral(None, None, None, None, 0)
    c = statistics.median(v)
    return ValorCentral(c, min(v), max(v), (c - preco) / c if c > 0 else None, len(v))
