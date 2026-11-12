from datetime import date, datetime, timedelta

import requests

from analise.modelo import Empresa, Fonte
from analise.verificacao import verificar

_URL_GLEIF = "https://api.gleif.org/api/v1/lei-records"
_BASE = "https://filings.xbrl.org"
_UA = {"User-Agent": "analise-acoes/1.0"}
# Nomes de país como o Yahoo os devolve (UE + EEE).
PAISES_UE_EEE = {
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Czechia", "Denmark",
    "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Ireland", "Italy", "Latvia",
    "Lithuania", "Luxembourg", "Malta", "Netherlands", "Poland", "Portugal", "Romania", "Slovakia",
    "Slovenia", "Spain", "Sweden", "Iceland", "Liechtenstein", "Norway",
}
# Conceitos por prioridade. Receita: algumas empresas (ex. ASML) usam RevenueFromContractsWithCustomers.
# Lucro: o atribuível aos acionistas é comparável com o "Net Income" do Yahoo.
_CONCEITOS = {
    "receita": ("ifrs-full:Revenue", "ifrs-full:RevenueFromContractsWithCustomers"),
    "lucro_liquido": ("ifrs-full:ProfitLossAttributableToOwnersOfParent", "ifrs-full:ProfitLoss"),
}
_DIMENSOES_BASE = {"concept", "entity", "period", "unit", "language"}


def lei_de(nome: str) -> str | None:
    r = requests.get(_URL_GLEIF, params={"filter[fulltext]": nome, "page[size]": 5},
                     headers=_UA, timeout=15)
    r.raise_for_status()
    dados = r.json().get("data") or []
    ativos = [d for d in dados if d["attributes"]["entity"].get("status") == "ACTIVE"] or dados
    alvo = nome.casefold()
    for ok in (lambda n: n == alvo, lambda n: n.startswith(alvo)):
        for d in ativos:
            if ok(d["attributes"]["entity"]["legalName"]["name"].casefold()):
                return d["id"]
    return dados[0]["id"] if dados else None


def _periodo(p: str) -> tuple[datetime, datetime]:
    ini, fim = p.split("/")
    return datetime.fromisoformat(ini), datetime.fromisoformat(fim)


def valores_xbrl(dados: dict) -> dict:
    """{ano, moeda, receita, lucro_liquido} do exercício anual mais recente de um xBRL-JSON."""
    achados: dict[tuple[datetime, str], tuple[int, float, str]] = {}  # (fim, campo) -> (prioridade, valor, moeda)
    for f in dados["facts"].values():
        d = f["dimensions"]
        campo = next((c for c, ks in _CONCEITOS.items() if d["concept"] in ks), None)
        if campo is None or set(d) - _DIMENSOES_BASE or "/" not in d.get("period", ""):
            continue
        ini, fim = _periodo(d["period"])
        if not 330 <= (fim - ini).days <= 400:
            continue
        prio = _CONCEITOS[campo].index(d["concept"])
        if (fim, campo) not in achados or prio < achados[(fim, campo)][0]:
            achados[(fim, campo)] = (prio, float(f["value"]), d["unit"].split(":")[-1])
    if not achados:
        return {}
    fim = max(k[0] for k in achados)
    out = {"ano": (fim - timedelta(days=1)).year}  # fim é exclusivo (meia-noite do dia seguinte)
    for (f, campo), (_, valor, moeda) in achados.items():
        if f == fim:
            out[campo], out["moeda"] = valor, moeda
    return out


def ultimo_relatorio(lei: str) -> tuple[Fonte, dict] | None:
    # JSON:API; confirmado em 2026-11: filter[entity.identifier]=LEI + sort=-period_end funciona.
    r = requests.get(f"{_BASE}/api/filings", headers=_UA, timeout=15,
                     params={"filter[entity.identifier]": lei, "sort": "-period_end", "page[size]": 1})
    r.raise_for_status()
    filings = r.json().get("data") or []
    if not filings:
        return None
    a = filings[0]["attributes"]
    if not a.get("json_url") or not a.get("viewer_url"):
        return None
    r = requests.get(_BASE + a["json_url"], headers=_UA, timeout=15)
    r.raise_for_status()
    valores = valores_xbrl(r.json())
    if "ano" not in valores:
        return None
    return Fonte("Relatório oficial (ESEF)", date.today().isoformat(), _BASE + a["viewer_url"]), valores


def enriquecer(e: Empresa) -> Empresa:
    """Liga ao relatório oficial ESEF e cruza receita/lucro (só UE/EEE). Nunca levanta."""
    if e.pais not in PAISES_UE_EEE:
        return e
    try:
        lei = lei_de(e.nome)
        rel = ultimo_relatorio(lei) if lei else None
    except (requests.RequestException, ValueError, KeyError):
        rel = None
    if rel is None:
        e.avisos.append("Relatório oficial não encontrado")
        return e
    fonte, oficial = rel
    e.links.append(fonte)
    e.avisos += verificar(e, oficial, fonte)
    return e
