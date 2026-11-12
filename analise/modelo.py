import math
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd


@dataclass(frozen=True)
class Fonte:
    nome: str
    data: str
    url: str | None = None


@dataclass(frozen=True)
class Dado:
    valor: float | None
    fonte: Fonte


@dataclass(frozen=True)
class Serie:
    valores: dict[int, float]
    fonte: Fonte

    def _validos(self) -> list[tuple[int, float]]:
        return sorted((a, v) for a, v in self.valores.items()
                      if v is not None and not math.isnan(v))

    def anos(self) -> list[int]:
        return [a for a, _ in self._validos()]

    def ultimo(self) -> float | None:
        v = self._validos()
        return v[-1][1] if v else None

    def ultimos(self, n: int) -> list[float]:
        return [v for _, v in self._validos()][-n:] if n > 0 else []


CAMPOS_ANUAIS: tuple[str, ...] = (
    "receita", "lucro_bruto", "ebit", "ebitda", "lucro_liquido",
    "resultado_antes_impostos", "impostos", "despesa_juros", "amortizacoes",
    "fluxo_operacional", "capex", "fcf", "eps", "acoes_media", "ativo_total",
    "ativo_corrente", "passivo_corrente", "passivo_total", "divida_total",
    "divida_longo_prazo", "caixa", "capital_proprio", "lucros_retidos",
    "imobilizado",
)

_SEM_FONTE = Fonte("", "")


def _dado() -> Dado:
    return Dado(None, _SEM_FONTE)


@dataclass
class Empresa:
    ticker: str = ""
    nome: str = ""
    bolsa: str = ""
    moeda: str = ""
    pais: str = ""
    setor: str = ""
    industria: str = ""
    descricao: str = ""
    e_financeira: bool = False
    preco: Dado = field(default_factory=_dado)
    acoes: Dado = field(default_factory=_dado)
    beta: Dado = field(default_factory=_dado)
    capitalizacao: Dado = field(default_factory=_dado)
    taxa_sem_risco: Dado = field(default_factory=_dado)
    anual: dict[str, Serie] = field(default_factory=dict)
    precos: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    dividendos: dict[int, float] = field(default_factory=dict)
    cambio_eur: Dado = field(default_factory=_dado)
    avisos: list[str] = field(default_factory=list)
    links: list[Fonte] = field(default_factory=list)


@dataclass
class ResultadoMetodo:
    nome: str
    valor_por_acao: float | None
    aplicavel: bool
    motivo: str = ""
    pressupostos: dict[str, float | str] = field(default_factory=dict)


@dataclass
class Criterio:
    descricao: str
    estado: Literal["ok", "falha", "nd"]
    valor: str


@dataclass
class ResultadoLente:
    investidor: str
    criterios: list[Criterio]
    valor_justo: float | None
    resumo: str
    nota: float | None = None


@dataclass
class Componente:
    nome: str
    peso: float
    nota: float | None
    detalhe: dict[str, float | None] = field(default_factory=dict)


@dataclass
class Pontuacao:
    total: float | None
    cobertura: float
    faixa: str
    dados_insuficientes: bool
    componentes: list[Componente]
