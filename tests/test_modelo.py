from analise.config import carregar
from analise.modelo import Empresa, Fonte, Serie


def test_serie_ordena_e_ignora_nan():
    s = Serie({2023: 3.0, 2021: 1.0, 2022: float("nan")}, Fonte("x", "2026-01-01"))
    assert s.anos() == [2021, 2023] and s.ultimo() == 3.0 and s.ultimos(5) == [1.0, 3.0]


def test_serie_vazia():
    s = Serie({}, Fonte("x", "2026-01-01"))
    assert s.anos() == [] and s.ultimo() is None and s.ultimos(3) == []


def test_empresa_parcial_e_config():
    e = Empresa(ticker="AAA")
    assert e.anual == {} and e.preco.valor is None and e.precos.empty
    assert carregar()["dcf"]["anos"] == 10
