from analise import servico
from analise.fontes import esef, sec, yahoo
from tests.test_yahoo import _carregar


def test_analisar_sequencia_completa(monkeypatch):
    _, e = _carregar("AAPL")
    chamadas = []
    monkeypatch.setattr(yahoo, "carregar_empresa", lambda t: e)
    monkeypatch.setattr(sec, "enriquecer", lambda emp, ua: chamadas.append(("sec", ua)) or emp)
    monkeypatch.setattr(esef, "enriquecer", lambda emp: chamadas.append(("esef",)) or emp)
    f = servico.analisar("AAPL", "eu@exemplo.pt")
    assert chamadas == [("sec", "eu@exemplo.pt"), ("esef",)]
    assert f.empresa is e
    assert len(f.metodos) == 9
    assert f.central.n_metodos == sum(m.aplicavel and m.valor_por_acao is not None for m in f.metodos)
    assert [l.investidor for l in f.lentes][:2] and len(f.lentes) == 6
    assert f.pontuacao.faixa in {"Boa", "Neutra", "Fraca", "Sem dados"}
    assert f.classificacao[0] in {"Crescimento", "Valor", "Misto"}
    assert f.risco in {"Baixo", "Médio", "Alto"}


def test_analisar_ticker_inexistente(monkeypatch):
    monkeypatch.setattr(yahoo, "carregar_empresa", lambda t: None)
    assert servico.analisar("ZZZZ", None) is None
