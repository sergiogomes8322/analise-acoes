from analise.indicadores import escala


def test_escala_linear():
    assert escala(0.05, -0.30, 0.40) == 50.0


def test_escala_limites():
    assert escala(9, 0, 1) == 100.0 and escala(-9, 0, 1) == 0.0


def test_escala_invertida():
    assert escala(2.0, 4.0, 0.0) == 50.0


def test_escala_none():
    assert escala(None, 0, 1) is None
