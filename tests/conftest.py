from analise.modelo import Empresa, Fonte, Serie

_F = Fonte("teste", "2026-01-01")


def fazer_empresa(anual: dict[str, dict[int, float]] | None = None, **campos) -> Empresa:
    """Empresa de teste: `anual={campo: {ano: valor}}` mais campos escalares de Empresa."""
    series = {k: Serie(dict(v), _F) for k, v in (anual or {}).items()}
    return Empresa(anual=series, **campos)
