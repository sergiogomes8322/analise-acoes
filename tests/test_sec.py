import json
from pathlib import Path

import pytest
import requests

from analise.fontes import sec
from analise.modelo import CAMPOS_ANUAIS, Empresa, Fonte, Serie

FIX = Path(__file__).parent / "fixtures"
DADOS = json.loads((FIX / "sec_aapl_companyfacts.json").read_text(encoding="utf-8"))
TICKERS = json.loads((FIX / "sec_tickers.json").read_text(encoding="utf-8"))
HOJE = "2026-11-11"
YF = Fonte("Yahoo Finance", HOJE)


class Resp:
    def __init__(self, dados):
        self._d = dados

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


def _empresa(anos=4, bolsa="NMS"):
    e = Empresa(ticker="AAPL", bolsa=bolsa, anual={c: Serie({}, YF) for c in CAMPOS_ANUAIS})
    e.anual["receita"] = Serie({2020 + i: 1.0 for i in range(anos)}, YF)
    return e


@pytest.fixture(autouse=True)
def _limpa():
    sec._mapa_tickers.cache_clear()


def _rede(monkeypatch, falha=None):
    chamadas = []

    def get(url, headers=None, timeout=None):
        chamadas.append((url, headers, timeout))
        if falha:
            raise falha
        return Resp(TICKERS if "company_tickers" in url else DADOS)

    monkeypatch.setattr(sec.requests, "get", get)
    return chamadas


def test_dez_anos_de_receita():
    s = sec.series_de_companyfacts(DADOS, HOJE, "0000320193")
    assert len(s["receita"].anos()) >= 10
    assert s["receita"].valores[2024] == 391035e6
    assert s["receita"].fonte.nome == "SEC EDGAR (10-K)"
    assert "CIK=0000320193" in s["receita"].fonte.url


def test_tag_alternativa_quando_falta_revenues():
    # a fixture não tem Revenues: usa RevenueFromContract... e SalesRevenueNet para os anos antigos
    assert "Revenues" not in DADOS["facts"]["us-gaap"]
    assert 2014 in sec.series_de_companyfacts(DADOS, HOJE, "1")["receita"].valores


def test_10q_e_periodos_curtos_ignorados_e_ultimo_arquivado_vence():
    ni = sec.series_de_companyfacts(DADOS, HOJE, "1")["lucro_liquido"].valores
    assert ni[2024] == 93736e6          # 10-Q (val 1, 2) e período de 9 meses (val 5) ignorados
    assert ni[2022] == 99803e6 + 7      # 10-K/A arquivado depois vence


def test_fcf_e_sem_valores_por_acao():
    s = sec.series_de_companyfacts(DADOS, HOJE, "1")
    assert s["fcf"].valores[2024] == (118254 - 9447) * 1e6
    assert not {"eps", "acoes_media", "dividendos"} & set(s)


def test_cik_de(monkeypatch):
    ch = _rede(monkeypatch)
    assert sec.cik_de("aapl", "ua-x") == "0000320193"
    assert sec.cik_de("ZZZZ", "ua-x") is None
    assert ch[0][1] == {"User-Agent": "ua-x"} and ch[0][2] == 15
    assert len(ch) == 1  # mapa em cache


def test_enriquecer_substitui_quando_sec_tem_mais_anos(monkeypatch):
    _rede(monkeypatch)
    e = sec.enriquecer(_empresa(), "ua-x")
    assert len(e.anual["receita"].anos()) >= 10
    assert e.anual["receita"].fonte.nome == "SEC EDGAR (10-K)"
    assert e.dividendos == {}
    assert e.links[-1].nome == "SEC EDGAR (10-K)" and e.avisos == []


def test_enriquecer_mantem_yahoo_se_sec_nao_tem_mais(monkeypatch):
    _rede(monkeypatch)
    e = sec.enriquecer(_empresa(anos=15), "ua-x")
    assert e.anual["receita"].fonte is YF


def test_sem_user_agent(monkeypatch):
    ch = _rede(monkeypatch)
    e = sec.enriquecer(_empresa(), None)
    assert ch == [] and "SEC não configurada" in e.avisos
    assert e.anual["receita"].fonte is YF


def test_fora_dos_eua(monkeypatch):
    ch = _rede(monkeypatch)
    e = sec.enriquecer(_empresa(bolsa="AMS"), "ua-x")
    assert ch == [] and e.avisos == []


def test_falha_de_rede(monkeypatch):
    _rede(monkeypatch, falha=requests.ConnectionError("x"))
    e = sec.enriquecer(_empresa(), "ua-x")
    assert "SEC indisponível" in e.avisos
    assert e.anual["receita"].fonte is YF and e.links == []


def test_mantem_yahoo_se_sec_desatualizada(monkeypatch):
    _rede(monkeypatch)
    e = _empresa()
    e.anual["receita"] = Serie({2025 + i: 1.0 for i in range(5)}, YF)  # menos anos, mas mais recente
    sec.enriquecer(e, "ua-x")
    assert e.anual["receita"].fonte is YF


def test_sem_uso_nao_adiciona_link(monkeypatch):
    _rede(monkeypatch)
    e = _empresa(anos=15)
    for c in CAMPOS_ANUAIS:
        e.anual[c] = Serie({2000 + i: 1.0 for i in range(30)}, YF)
    e.dividendos = {2000 + i: 1.0 for i in range(30)}
    sec.enriquecer(e, "ua-x")
    assert e.links == []


def test_falha_do_mapa_nao_fica_em_cache(monkeypatch):
    _rede(monkeypatch, falha=requests.ConnectionError("x"))
    with pytest.raises(requests.ConnectionError):
        sec.cik_de("AAPL", "ua-x")
    _rede(monkeypatch)
    assert sec.cik_de("AAPL", "ua-x") == "0000320193"


def test_enriquecer_verifica_contra_yahoo_em_usd(monkeypatch):
    _rede(monkeypatch)
    s = sec.series_de_companyfacts(DADOS, HOJE, "0000320193")
    ano = max(s["receita"].anos())
    e = _empresa(anos=15)
    e.moeda = "USD"
    e.anual["receita"] = Serie({ano: s["receita"].valores[ano] * 1.05}, YF)
    e = sec.enriquecer(e, "ua-x")
    assert len(e.avisos) == 1 and e.avisos[0].startswith(f"⚠️ Receita {ano}: Yahoo")


def test_enriquecer_nao_verifica_se_moeda_nao_usd(monkeypatch):
    _rede(monkeypatch)
    e = _empresa(anos=15)
    e.moeda = "EUR"
    assert sec.enriquecer(e, "ua-x").avisos == []


def test_por_acao_nunca_substituido_pela_sec(monkeypatch):
    # SEC não ajusta desdobramentos (AAPL 4:1 em 2020): EPS, ações e dividendos ficam os do Yahoo
    from analise import indicadores
    from tests.test_yahoo import _carregar
    _rede(monkeypatch)
    _, e = _carregar("AAPL")
    e.ticker, e.moeda = "AAPL", "EUR"  # EUR: sem verificação cruzada, o teste é só a substituição
    for campo in ("eps", "acoes_media", "receita"):
        e.anual[campo] = Serie({a: v for a, v in e.anual[campo].valores.items() if a in (2023, 2024)},
                               e.anual[campo].fonte)
    e.dividendos = {2023: 0.95, 2024: 0.99}
    eps, acoes, divs = e.anual["eps"], e.anual["acoes_media"], dict(e.dividendos)
    sec.enriquecer(e, "ua-x")
    assert e.anual["receita"].fonte.nome == "SEC EDGAR (10-K)"  # totais continuam a vir da SEC
    assert e.anual["eps"] is eps and e.anual["acoes_media"] is acoes and e.dividendos == divs
    assert abs(indicadores.diluicao_anual(e)) < 0.05


def test_facto_malformado_nao_rebenta(monkeypatch):
    d = json.loads(json.dumps(DADOS))
    del d["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0]["end"]
    monkeypatch.setattr(sec.requests, "get",
                        lambda url, headers=None, timeout=None: Resp(TICKERS if "company_tickers" in url else d))
    e = sec.enriquecer(_empresa(), "ua-x")
    assert "SEC indisponível" in e.avisos and e.anual["receita"].fonte is YF
