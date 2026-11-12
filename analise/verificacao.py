from analise.config import carregar
from analise.modelo import Empresa, Fonte

_CAMPOS = (("receita", "Receita"), ("lucro_liquido", "Lucro líquido"))


def _milhoes(v: float) -> str:
    return f"{v / 1e6:,.1f}".replace(",", " ").replace(".", ",") + " M"


def verificar(e: Empresa, oficial: dict, fonte: Fonte) -> list[str]:
    """Avisos quando receita/lucro do Yahoo divergem do relatório oficial (`fonte`) do mesmo ano."""
    if oficial.get("moeda") != e.moeda:
        return [f"Relatório oficial em {oficial.get('moeda')}: verificação não feita"]
    limite = carregar()["verificacao"]["divergencia_max"]
    ano, avisos = oficial["ano"], []
    for campo, rotulo in _CAMPOS:
        serie, ref = e.anual.get(campo), oficial.get(campo)
        yahoo = serie.valores.get(ano) if serie else None
        if yahoo is None or not ref:
            continue
        dif = abs(yahoo - ref) / abs(ref)
        if dif > limite:
            z = f"{dif * 100:.1f}".replace(".", ",")
            avisos.append(f"⚠️ {rotulo} {ano}: Yahoo {_milhoes(yahoo)} vs relatório oficial "
                          f"{_milhoes(ref)} (dif. {z} %)")
    return avisos
