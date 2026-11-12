import json
from pathlib import Path

import requests

from analise import verificacao
from analise.fontes import esef
from analise.modelo import Empresa, Fonte, Serie

FIX = Path(__file__).parent / "fixtures"
GLEIF = json.loads((FIX / "gleif_asml.json").read_text(encoding="utf-8"))
FILINGS = json.loads((FIX / "xbrl_filings_asml.json").read_text(encoding="utf-8"))
XBRL = json.loads((FIX / "xbrl_asml.json").read_text(encoding="utf-8"))
LEI = "724500Y6DUVHQD6OXN27"
YF = Fonte("Yahoo Finance", "2026-11-11")
OFICIAL = Fonte("Relatório oficial (ESEF)", "2026-11-11", "https://x")


class Resp:
    def __init__(self, dados):
        self._d = dados

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


def _empresa(receita=100.0, lucro=10.0, moeda="EUR", pais="Netherlands"):
    return Empresa(ticker="ASML.AS", nome="ASML Holding", moeda=moeda, pais=pais,
                   anual={"receita": Serie({2025: receita}, YF), "lucro_liquido": Serie({2025: lucro}, YF)})


def _rede(monkeypatch, filings=FILINGS, falha=None):
    def get(url, params=None, headers=None, timeout=None):
        if falha:
            raise falha
        if "gleif" in url:
            return Resp(GLEIF)
        if url.endswith(".json"):
            return Resp(XBRL)
        return Resp(filings)

    monkeypatch.setattr(esef.requests, "get", get)


def test_verificar_divergencia_5pct_avisa():
    av = verificacao.verificar(_empresa(receita=105e6), {"ano": 2025, "moeda": "EUR", "receita": 100e6}, OFICIAL)
    assert av == ["⚠️ Receita 2025: Yahoo 105,0 M vs relatório oficial 100,0 M (dif. 5,0 %) — fonte: Relatório oficial (ESEF)"]


def test_verificar_1pct_nao_avisa():
    assert verificacao.verificar(_empresa(receita=101e6), {"ano": 2025, "moeda": "EUR", "receita": 100e6}, OFICIAL) == []


def test_verificar_formato_pt_e_lucro():
    e = _empresa(lucro=30_000_000_000.0)
    av = verificacao.verificar(e, {"ano": 2025, "moeda": "EUR", "lucro_liquido": 28_262_900_000.0}, OFICIAL)
    assert av == ["⚠️ Lucro líquido 2025: Yahoo 30 000,0 M vs relatório oficial 28 262,9 M (dif. 6,1 %) — fonte: Relatório oficial (ESEF)"]


def test_verificar_moeda_diferente_salta():
    av = verificacao.verificar(_empresa(moeda="USD", receita=200.0), {"ano": 2025, "moeda": "EUR", "receita": 100.0}, OFICIAL)
    assert av == ["Relatório oficial em EUR: verificação não feita"]


def test_verificar_sem_ano_ou_campo_nao_avisa():
    assert verificacao.verificar(_empresa(), {"ano": 2024, "moeda": "EUR", "receita": 1.0}, OFICIAL) == []
    assert verificacao.verificar(_empresa(), {"ano": 2025, "moeda": "EUR"}, OFICIAL) == []


def test_lei_de(monkeypatch):
    _rede(monkeypatch)
    assert esef.lei_de("ASML Holding") == LEI


def test_lei_de_sem_resultados(monkeypatch):
    monkeypatch.setattr(esef.requests, "get", lambda *a, **k: Resp({"data": []}))
    assert esef.lei_de("xxx") is None


def test_parse_xbrl_json_ignora_dimensoes_e_usa_ultimo_ano():
    assert esef.valores_xbrl(XBRL) == {"ano": 2025, "moeda": "EUR",
                                       "receita": 32667300000.0, "lucro_liquido": 10213000000.0}


def test_ultimo_relatorio(monkeypatch):
    _rede(monkeypatch)
    fonte, v = esef.ultimo_relatorio(LEI)
    assert fonte.url == "https://filings.xbrl.org" + FILINGS["data"][0]["attributes"]["viewer_url"]
    assert v["receita"] == 32667300000.0 and v["ano"] == 2025


def test_ultimo_relatorio_sem_json_url(monkeypatch):
    sem = {"data": [{"attributes": {"period_end": "2025-12-31", "viewer_url": "/a/b.html"}}]}
    _rede(monkeypatch, filings=sem)
    assert esef.ultimo_relatorio(LEI) is None


def test_enriquecer_acrescenta_link_e_aviso(monkeypatch):
    _rede(monkeypatch)
    e = esef.enriquecer(_empresa(receita=30e9, lucro=10.213e9))
    assert e.links[-1].url.endswith("ixbrlviewer.html")
    assert len(e.avisos) == 1 and e.avisos[0].startswith("⚠️ Receita 2025")


def test_enriquecer_sem_json_url_avisa(monkeypatch):
    _rede(monkeypatch, filings={"data": [{"attributes": {"viewer_url": "/a"}}]})
    e = esef.enriquecer(_empresa())
    assert e.avisos == ["Relatório oficial não encontrado"] and e.links == []


def test_enriquecer_falha_de_rede(monkeypatch):
    _rede(monkeypatch, falha=requests.ConnectionError("x"))
    assert esef.enriquecer(_empresa()).avisos == ["Relatório oficial não encontrado"]


def test_enriquecer_fora_da_ue(monkeypatch):
    _rede(monkeypatch, falha=AssertionError("não devia chamar"))
    e = esef.enriquecer(_empresa(pais="United States"))
    assert e.avisos == [] and e.links == []


def test_lucro_atribuivel_tem_prioridade_sobre_profitloss():
    d = json.loads(json.dumps(XBRL))
    base = next(f for f in d["facts"].values() if f["dimensions"]["concept"] == "ifrs-full:ProfitLoss"
                and f["dimensions"]["period"].startswith("2025"))
    d["facts"]["x"] = {"value": "9000000000.0", "dimensions": {**base["dimensions"],
                       "concept": "ifrs-full:ProfitLossAttributableToOwnersOfParent"}}
    assert esef.valores_xbrl(d)["lucro_liquido"] == 9000000000.0


def _hit(lei, nome, status="ACTIVE"):
    return {"id": lei, "attributes": {"entity": {"legalName": {"name": nome}, "status": status}}}


def test_lei_de_prefere_ativo_com_nome_igual(monkeypatch):
    hits = {"data": [_hit("A", "ASML Holding NV ADRhedged(TM)"), _hit("B", "ASML Holding N.V.", "INACTIVE"),
                     _hit("C", "asml holding"), _hit("D", "ASML Holding N.V.")]}
    monkeypatch.setattr(esef.requests, "get", lambda *a, **k: Resp(hits))
    assert esef.lei_de("ASML Holding") == "C"


def test_lei_de_startswith_e_segundo_hit(monkeypatch):
    hits = {"data": [_hit("A", "Outra Empresa"), _hit("B", "ASML Holding N.V.")]}
    monkeypatch.setattr(esef.requests, "get", lambda *a, **k: Resp(hits))
    assert esef.lei_de("ASML Holding") == "B"
