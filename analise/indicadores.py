def escala(x: float | None, zero: float, cem: float) -> float | None:
    """Interpolacao linear limitada a [0, 100]; zero > cem inverte a escala."""
    if x is None:
        return None
    return max(0.0, min(100.0, (x - zero) / (cem - zero) * 100.0))
