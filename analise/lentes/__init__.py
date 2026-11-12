from analise.lentes import ackman, buffett, druckenmiller, graham, greenblatt, lynch
from analise.modelo import Empresa, ResultadoLente


def todas(e: Empresa) -> list[ResultadoLente]:
    return [m.avaliar(e) for m in (buffett, graham, lynch, ackman, greenblatt, druckenmiller)]
