# App de Análise de Ações — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir uma app Streamlit, usável no telemóvel. Escreve-se um nome ou ticker e ela mostra uma ficha com: breve análise, valor intrínseco por vários métodos, lentes de investidores e pontuação 0–100 com risco, sempre com as fontes.

**Architecture:**
- **Três camadas:** `analise/fontes/` (rede), `analise/modelo.py` (dados + origem) e cálculos puros (`indicadores`, `valor/`, `lentes/`, `perfil`, `pontuacao`).
- **`app.py` só apresenta.**
- **Testes:** todo o código de cálculo é testado offline com números fixos. As fontes são testadas com fixtures gravadas.

**Tech Stack:** Python 3.13 (uv), streamlit, yfinance, pandas, requests, pytest, tomllib (stdlib).

**Spec:** `docs/superpowers/specs/2026-11-11-analise-acoes-design.md`

## Global Constraints

- **Custo:** 0 €. Nenhuma API paga, nenhuma chave paga.
- **Fontes permitidas:**
  - Yahoo Finance (yfinance), SEC EDGAR, filings.xbrl.org, GLEIF e BCE.
  - **Nunca** TradingView nem qualquer scraping que viole os termos de uso.
- **Cada número na ficha mostra a sua fonte:** nome, data e link quando existir.
- **Dado em falta:** `None` e "N/D" com motivo. **Nunca** 0 nem uma estimativa silenciosa.
- **Interface em português de Portugal.** Os valores aparecem na moeda da cotação e em EUR ao lado quando a moeda for outra.
- **Avisos fixos na ficha:**
  - Rodapé: "Informação educativa, não é aconselhamento financeiro."
  - Lentes: "As lentes são interpretações de princípios públicos destes investidores, não as suas opiniões."
- **Pontuação:**
  - Faixas: ≥ 78 "Boa", 60–77 "Neutra", < 60 "Fraca".
  - Com cobertura < 60 % nunca aparece "Boa".
- **Cache:** `st.cache_data(ttl=12*3600)` em todas as chamadas de rede.
- **Configuração:** todos os limites, pesos e taxas ficam em `config.toml`; nenhum número mágico no código de cálculo.
- **Segredos:**
  - O contacto do `User-Agent` da SEC vem de `st.secrets["SEC_USER_AGENT"]` ou da variável de ambiente `SEC_USER_AGENT`. Nunca fica no código nem no git.
  - Sem contacto configurado, a SEC é ignorada com um aviso.
- **Ensino:** em cada tarefa, o executor explica ao Sergio em 5–10 linhas o que foi feito e porquê. Comentários no código só para o "porquê".
- **Testes:** `uv run pytest` sem acesso à rede.

## Review Focus

1. **Ticker inexistente, ou nome com 0 resultados:** mostra "Não encontrei esta ação" sem rebentar. Teste na Tarefa 2.
2. **Yahoo devolve balanços vazios ou com colunas NaN:** as séries ficam vazias e os métodos dizem "N/D", nunca 0 nem exceção. Teste na Tarefa 2.
3. **EPS, FCF ou capital próprio negativos:** os métodos dependentes ficam `aplicavel=False` com motivo. Nunca há valores negativos nem `sqrt` de negativo. Teste na Tarefa 6.
4. **Moeda dos balanços (`financialCurrency`) diferente da moeda da cotação**, ou cotação em GBp: tudo é convertido para a moeda da cotação antes dos cálculos. Teste na Tarefa 2.
5. **Uma fonte secundária falha (BCE, SEC, ESEF, GLEIF):** a ficha aparece na mesma, com valor por defeito ou sem link, e um aviso em `Empresa.avisos`. Testes nas Tarefas 5, 10 e 11.

---

## Estrutura de ficheiros

```
pyproject.toml, .gitignore, config.toml, README.md
.streamlit/config.toml            # tema, sem segredos
app.py                            # interface
analise/__init__.py
analise/config.py                 # carrega config.toml
analise/modelo.py                 # Fonte, Dado, Serie, Empresa, ResultadoMetodo, Criterio, ResultadoLente, Componente, Pontuacao
analise/indicadores.py            # funções puras sobre séries e preços
analise/fontes/yahoo.py           # pesquisa + Empresa a partir do Yahoo
analise/fontes/taxas.py           # taxa sem risco + câmbio (BCE, ^TNX, defeitos)
analise/fontes/sec.py             # histórico EUA (companyfacts)
analise/fontes/esef.py            # GLEIF + filings.xbrl.org: link + verificação
analise/valor/dcf.py              # DCF 2 fases + owner earnings
analise/valor/outros.py           # Graham, EPV, múltiplos, Gordon, P/B bancos
analise/valor/central.py          # mediana + intervalo + margem
analise/perfil.py                 # crescimento/valor, alertas, etiqueta de risco
analise/pontuacao.py
analise/lentes/{buffett,graham,lynch,ackman,greenblatt,druckenmiller}.py
analise/servico.py                # analisar(ticker) -> Ficha (junta tudo)
tests/fixtures/                   # dados gravados (json/csv)
tests/test_*.py
```

---

### Task 1: Projeto base, configuração e modelo de dados

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `config.toml`, `analise/__init__.py`, `analise/config.py`, `analise/modelo.py`, `analise/indicadores.py`
- Test: `tests/test_modelo.py`, `tests/test_escala.py`

**Interfaces:**
- Produces:
  - `analise.config.carregar() -> dict`: lê `config.toml` na raiz, com cache em memória.
  - `analise.modelo`:
    - `Fonte(nome: str, data: str, url: str | None = None)`, frozen.
    - `Dado(valor: float | None, fonte: Fonte)`, frozen.
    - `Serie(valores: dict[int, float], fonte: Fonte)`, frozen. Tem `.anos() -> list[int]` (ordem crescente), `.ultimo() -> float | None` e `.ultimos(n) -> list[float]`, por ordem cronológica e sem NaN.
    - `Empresa`, dataclass com:
      - perfil: `ticker`, `nome`, `bolsa`, `moeda`, `pais`, `setor`, `industria`, `descricao: str`, `e_financeira: bool`;
      - cotação: `preco`, `acoes`, `beta`, `capitalizacao`, `taxa_sem_risco: Dado`;
      - séries: `anual: dict[str, Serie]`, `precos: pandas.Series` (fecho diário, 5 anos, índice de datas), `dividendos: dict[int, float]` (DPS por ano);
      - extra: `cambio_eur: Dado` (1 unidade da moeda = x EUR), `avisos: list[str]`, `links: list[Fonte]`.
    - `CAMPOS_ANUAIS: tuple[str, ...]`: `receita, lucro_bruto, ebit, ebitda, lucro_liquido, resultado_antes_impostos, impostos, despesa_juros, amortizacoes, fluxo_operacional, capex, fcf, eps, acoes_media, ativo_total, ativo_corrente, passivo_corrente, passivo_total, divida_total, divida_longo_prazo, caixa, capital_proprio, lucros_retidos, imobilizado`.
    - `ResultadoMetodo(nome: str, valor_por_acao: float | None, aplicavel: bool, motivo: str, pressupostos: dict[str, float | str])`.
    - `Criterio(descricao: str, estado: Literal["ok", "falha", "nd"], valor: str)`.
    - `ResultadoLente(investidor: str, criterios: list[Criterio], valor_justo: float | None, resumo: str, nota: float | None = None)`.
    - `Componente(nome: str, peso: float, nota: float | None, detalhe: dict[str, float | None])`.
    - `Pontuacao(total: float | None, cobertura: float, faixa: str, dados_insuficientes: bool, componentes: list[Componente])`.
  - `analise.indicadores.escala(x: float | None, zero: float, cem: float) -> float | None`: interpolação linear limitada a [0, 100]. Funciona com `zero > cem` (escala invertida). `None` → `None`.

- [ ] **Step 1: Inicializar o repositório e o projeto**

Run:
```
git init
uv init --app --python 3.13 --name analise-acoes
uv add streamlit yfinance pandas requests
uv add --dev pytest
```
`.gitignore`: `.venv/`, `__pycache__/`, `.streamlit/secrets.toml`, `.pytest_cache/`.

- [ ] **Step 2: Escrever `config.toml` com os valores do spec**

```toml
[dcf]
premio_mercado = 0.055
desconto_minimo = 0.08
crescimento_terminal = 0.025
crescimento_max = 0.20
anos = 10
beta_defeito = 1.0

[graham]
g_max = 15.0
spread_aaa = 0.01

[impostos]
taxa_defeito = 0.25

[historico]
anos_pedidos = 5
anos_minimos = 3

[sem_risco_defeito]          # valores por defeito; definidos em 2026-11-11, rever
data = "2026-11-11"
EUR = 0.027
USD = 0.042
GBP = 0.045
CHF = 0.008
SEK = 0.025
DKK = 0.025
NOK = 0.039
OUTRA = 0.04

[pontuacao.pesos]
valorizacao = 0.30
qualidade = 0.25
solidez = 0.20
risco_mercado = 0.15
tendencia = 0.10

[pontuacao.faixas]
boa = 78
neutra = 60
cobertura_minima = 0.60

# [zero, cem] por sub-indicador (spec §11)
[pontuacao.limites]
margem_seguranca = [-0.30, 0.40]
roic = [0.05, 0.25]
cv_margem_operacional = [0.5, 0.1]
anos_receita_a_crescer = [0.0, 1.0]
divida_liquida_ebitda = [4.0, 0.0]
cobertura_juros = [1.5, 10.0]
altman_z = [1.8, 3.0]
piotroski_f = [0, 9]
beta = [1.8, 0.8]
volatilidade = [0.50, 0.20]
queda_maxima = [0.65, 0.25]
preco_vs_mm200 = [-0.20, 0.20]
momento_12_1 = [-0.30, 0.30]

[alertas]
volatilidade = 0.40
queda_maxima = 0.50
beta = 1.5
divida_liquida_ebitda = 3.0
diluicao_anual = 0.03
altman_z = 1.8
cobertura_juros = 3.0

[perfil]
crescimento_cagr = 0.15
crescimento_pe = 25
crescimento_pe_g = 0.10
valor_pe = 15
valor_pb = 1.5

[verificacao]
divergencia_max = 0.02
```

- [ ] **Step 3: Escrever os testes que falham**

```python
# tests/test_escala.py
from analise.indicadores import escala
def test_escala_linear():      assert escala(0.05, -0.30, 0.40) == 50.0
def test_escala_limites():     assert escala(9, 0, 1) == 100.0 and escala(-9, 0, 1) == 0.0
def test_escala_invertida():   assert escala(2.0, 4.0, 0.0) == 50.0
def test_escala_none():        assert escala(None, 0, 1) is None

# tests/test_modelo.py
from analise.modelo import Serie, Fonte
def test_serie_ordena_e_ignora_nan():
    s = Serie({2023: 3.0, 2021: 1.0, 2022: float("nan")}, Fonte("x", "2026-01-01"))
    assert s.anos() == [2021, 2023] and s.ultimo() == 3.0 and s.ultimos(5) == [1.0, 3.0]
```

- [ ] **Step 4: Correr e confirmar que falha**

Run: `uv run pytest -q`. Expected: FAIL (ImportError).

- [ ] **Step 5: Implementar `analise/config.py`, `analise/modelo.py` e `escala` em `analise/indicadores.py`**

- [ ] **Step 6: Correr e confirmar que passa**

Run: `uv run pytest -q`. Expected: 5 passed.

- [ ] **Step 7: Commit**

`git add -A; git commit -m "feat: project skeleton, config and data model"`

---

### Task 2: Fonte Yahoo (pesquisa + Empresa)

**Files:**
- Create: `analise/fontes/__init__.py`, `analise/fontes/yahoo.py`, `tests/fixtures/yahoo_*.json`, `tests/test_yahoo.py`

**Interfaces:**
- Consumes: `modelo.*`, `config.carregar()`.
- Produces:
  - `Correspondencia(ticker: str, nome: str, bolsa: str, tipo: str)`, dataclass.
  - `pesquisar(texto: str) -> list[Correspondencia]`, via `yfinance.Search(texto).quotes`. Filtra `quoteType == "EQUITY"`. `[]` se não houver nada ou se a rede falhar.
  - `empresa_de_dados(info: dict, demonstracoes: dict[str, pandas.DataFrame], precos: pandas.Series, dividendos: pandas.Series, hoje: str) -> Empresa`. É **pura** e testável. As `demonstracoes` têm as chaves `"income"`, `"balance"` e `"cashflow"`, no formato `yf.Ticker.income_stmt`: linhas são rótulos, colunas são datas.
  - `carregar_empresa(ticker: str) -> Empresa | None`: chama o yfinance e depois `empresa_de_dados`. Devolve `None` se `info` vier sem preço.

Mapeamento de rótulos yfinance → `CAMPOS_ANUAIS` (constante `MAPA` em `yahoo.py`):

```
receita=Total Revenue; lucro_bruto=Gross Profit; ebit=EBIT; ebitda=EBITDA; lucro_liquido=Net Income;
resultado_antes_impostos=Pretax Income; impostos=Tax Provision; despesa_juros=Interest Expense;
amortizacoes=Depreciation And Amortization; fluxo_operacional=Operating Cash Flow;
capex=Capital Expenditure (guardar valor absoluto); fcf=Free Cash Flow; eps=Diluted EPS;
acoes_media=Diluted Average Shares; ativo_total=Total Assets; ativo_corrente=Current Assets;
passivo_corrente=Current Liabilities; passivo_total=Total Liabilities Net Minority Interest;
divida_total=Total Debt; divida_longo_prazo=Long Term Debt; caixa=Cash And Cash Equivalents;
capital_proprio=Stockholders Equity; lucros_retidos=Retained Earnings; imobilizado=Net PPE
```

Regras:
- **Moeda:**
  - Se `info["currency"] == "GBp"`: preço e histórico ÷ 100 e `moeda = "GBP"`. O mesmo vale para `"ZAc"` e `"ILA"`.
  - Se `info["financialCurrency"]` for diferente da moeda da cotação, os campos monetários (todos exceto `acoes_media`) são convertidos com `taxas.cambio(de, para)` da Tarefa 5. Até a Tarefa 5 existir, injeta-se a função de conversão como parâmetro `converter: Callable[[str, str], float | None]`.
  - Se a conversão falhar: séries monetárias vazias e o aviso "Balanços em X sem conversão disponível".
- **`e_financeira`:** `setor == "Financial Services"` e a `industria` contém "Bank" ou "Insurance".
- **`dividendos`:** soma por ano civil, só de anos completos.
- **`Fonte`:** `Fonte("Yahoo Finance", hoje, f"https://finance.yahoo.com/quote/{ticker}")`.

- [ ] **Step 1: Gravar fixtures**

Corre uma vez um script descartável (fora de `tests/`) que grava `info`, as 3 demonstrações e 5 anos de preços. Grava para `ASML.AS` (EUR), `SHEL.L` (GBp na cotação, balanços em USD) e `AAPL`, em `tests/fixtures/yahoo_<ticker>.json`. Cria à mão `yahoo_vazio.json`: `info` com preço, demonstrações vazias.

- [ ] **Step 2: Escrever os testes que falham**

```python
def test_asml_basico():          # moeda EUR, receita 4 anos, preço > 0, fonte Yahoo
def test_shel_gbp_e_conversao():  # moeda == "GBP", preço == info price / 100; receita convertida com converter fake 0.8
def test_balancos_vazios():       # anual vazio ou séries sem valores; nenhuma exceção; preço presente
def test_capex_positivo():        # capex guardado em valor absoluto
def test_pesquisar_sem_resultados(monkeypatch):  # Search devolve quotes=[] → []
```

- [ ] **Step 3: Correr e confirmar que falha.** `uv run pytest tests/test_yahoo.py -q` → FAIL.
- [ ] **Step 4: Implementar `yahoo.py` conforme as Interfaces e Regras acima.**
- [ ] **Step 5: Correr e confirmar que passa.** `uv run pytest -q` → todos passam.
- [ ] **Step 6: Commit.** `git commit -m "feat: Yahoo source with currency normalisation"`

---

### Task 3: Teste de viabilidade na nuvem (portão de decisão)

Objetivo do spec: confirmar se o Yahoo responde a partir da Streamlit Community Cloud **antes** de construir o resto.

**Files:**
- Create: `app.py` (versão mínima): campo de pesquisa → lista de `pesquisar()` → `carregar_empresa()` → nome, preço, moeda, número de anos de receita.

**Interfaces:** Consumes `yahoo.pesquisar`, `yahoo.carregar_empresa`.

- [ ] **Step 1: Escrever o `app.py` mínimo, com `st.cache_data(ttl=43200)` nas duas chamadas.**
- [ ] **Step 2: Testar localmente.** `uv run streamlit run app.py`. Pesquisar `ASML`, `Jerónimo Martins`, `SHEL.L`, `AAPL`, `NESN.SW`. Expected: os 5 mostram preço.
- [ ] **Step 3: Publicar (precisa do Sergio).**
  1. O Sergio corre `gh auth login`.
  2. **Pedir confirmação ao Sergio antes de criar o repositório no GitHub**, porque publicar código é uma ação externa. Repositório privado.
  3. Criá-lo com `gh repo create analise-acoes --private --source . --push`.
  4. Gerar `requirements.txt` com `uv export --no-hashes --no-dev -o requirements.txt`; a Streamlit Cloud lê esse ficheiro.
  5. O Sergio entra em share.streamlit.io com o GitHub, escolhe "New app", o repositório e `app.py`.
- [ ] **Step 4: Testar os mesmos 5 tickers no link público, no telemóvel.**
  - Se ≥ 4 funcionarem: segue o plano.
  - Se não: regista em `README.md` "Modo local: correr no PC" e segue o plano na mesma, porque os cálculos não mudam. Informa o Sergio.
- [ ] **Step 5: Commit.** `git commit -m "feat: minimal app for cloud viability test"`

---

### Task 4: Indicadores financeiros (funções puras)

**Files:**
- Modify: `analise/indicadores.py`
- Test: `tests/test_indicadores.py`

**Interfaces:**
- Produces, todos `float | None` e `None` quando faltam dados:
  - `cagr(serie: Serie, anos_max: int) -> tuple[float | None, int]`: devolve (taxa, nº de anos usados). `None` se o início ou o fim forem ≤ 0, ou se houver menos de 2 pontos.
  - `media(valores: list[float]) -> float | None`.
  - `coef_variacao(valores: list[float]) -> float | None`: desvio padrão / |média|.
  - `fracao_anos_a_crescer(serie: Serie) -> float | None`.
  - `volatilidade_anual(precos) -> float | None`: desvio dos retornos diários do último ano × √252.
  - `queda_maxima(precos) -> float | None`: valor positivo, por exemplo 0.35.
  - `preco_vs_mm200(precos) -> float | None`.
  - `momento(precos, meses: int, saltar_meses: int = 0) -> float | None`. Usa 21 dias úteis por mês.
  - `roic(e: Empresa, ano: int) -> float | None`: EBIT×(1−t) / (capital próprio + dívida − caixa).
  - `roe(e, ano)`.
  - `margem_operacional(e, ano)`.
  - `divida_liquida_ebitda(e) -> float | None`: último ano. Com EBITDA ≤ 0 devolve `None`.
  - `cobertura_juros(e)`: com juros = 0 devolve `None`.
  - `altman_z(e) -> float | None`: fórmula original `1.2·WC/TA + 1.4·RE/TA + 3.3·EBIT/TA + 0.6·MVE/TL + 1.0·Vendas/TA`, com MVE = capitalização.
  - `piotroski_f(e) -> int | None`: os 9 critérios clássicos com os 2 últimos anos. `None` se faltar o ano anterior.
  - `diluicao_anual(e) -> float | None`: CAGR de `acoes_media`.
  - `taxa_imposto(e) -> float`: média de impostos / resultado antes de impostos dos anos com resultado > 0, limitada a [0, 0.5]. Sem dados, usa `impostos.taxa_defeito`.

- [ ] **Step 1: Testes que falham, com números calculados à mão:**

```python
def test_cagr():                 # 100 → 121 em 2 anos → (0.10, 2)
def test_cagr_negativo_none():   # início -5 → (None, ...)
def test_volatilidade():         # série com retornos alternados +1%/-1% → ≈ 0.01*sqrt(252)
def test_queda_maxima():         # 100,120,60,90 → 0.5
def test_preco_vs_mm200():       # 200 dias a 100, último 110 → ≈ 0.0995 (mm inclui o último)
def test_altman_z():             # valores escolhidos → resultado esperado à mão
def test_piotroski_perfeito():   # 2 anos a melhorar em tudo → 9
def test_ebitda_negativo():      # divida_liquida_ebitda → None
```

- [ ] **Step 2: Correr e confirmar que falha.** `uv run pytest tests/test_indicadores.py -q` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Correr e confirmar que passa.**
- [ ] **Step 5: Commit.** `git commit -m "feat: financial indicators"`

---

### Task 5: Taxa sem risco e câmbio

**Files:**
- Create: `analise/fontes/taxas.py`, `tests/fixtures/bce_*.csv`, `tests/test_taxas.py`
- Modify: `analise/fontes/yahoo.py`: `carregar_empresa` passa a preencher `taxa_sem_risco` e `cambio_eur`, e usa `taxas.cambio` como `converter`.

**Interfaces:**
- Produces:
  - `taxa_sem_risco(moeda: str, hoje: str) -> tuple[Dado, str | None]`: devolve o dado e um aviso opcional.
    - **EUR:** BCE `https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?lastNObservations=1&format=csvdata`, coluna `OBS_VALUE` em %, dividida por 100.
    - **USD:** `yf.Ticker("^TNX")`, último fecho ÷ 100.
    - **Outras moedas, ou falha:** `config.sem_risco_defeito[moeda]` (ou `OUTRA`), com o aviso "Taxa sem risco por defeito (definida em {data})".
  - `cambio(de: str, para: str) -> float | None`: taxas de referência BCE `EXR/D.{MOEDA}.EUR.SP00.A` (unidades de moeda por 1 EUR), cruzadas via EUR. `de == para` → 1.0. Falha → `None`.
  - `para_eur(moeda: str) -> Dado`.
  - Funções `_ler_csv_bce(texto: str) -> float | None` puras, para os testes.

- [ ] **Step 1: Testes que falham:** parse dos CSV gravados; `cambio("USD", "GBP")` com duas taxas fixas monkeypatched; rede a falhar (`requests` levanta exceção) → valor por defeito + aviso.
- [ ] **Step 2: Correr e confirmar que falha.**
- [ ] **Step 3: Implementar.** `requests` com `timeout=10`. A cache fica no `app` (Tarefa 12), não aqui.
- [ ] **Step 4: Correr e confirmar que passa.**
- [ ] **Step 5: Commit.** `git commit -m "feat: risk-free rate and FX from ECB with defaults"`

---

### Task 6: DCF e owner earnings

**Files:**
- Create: `analise/valor/__init__.py`, `analise/valor/dcf.py`, `tests/test_dcf.py`

**Interfaces:**
- Consumes: `Empresa`, `indicadores.cagr`, `config`.
- Produces:
  - `taxa_desconto(e: Empresa) -> float`: `max(rf + premio_mercado × beta, desconto_minimo)`. Sem beta, usa `beta_defeito`.
  - `valor_presente(base: float, g0: float, gT: float, r: float, anos: int) -> float`.
  - `dcf(e: Empresa) -> ResultadoMetodo`.
  - `owner_earnings(e: Empresa) -> ResultadoMetodo`.

Algoritmo de `valor_presente` (decisão do spec §9):

```
para t em 1..anos: g_t = g0 + (gT − g0)·(t−1)/(anos−1); fluxo_t = fluxo_{t−1}·(1+g_t); VP += fluxo_t/(1+r)^t
terminal = fluxo_anos·(1+gT)/(r − gT);  VP += terminal/(1+r)^anos
```

Regras:
- **Base do DCF:** média do FCF dos últimos 3 anos disponíveis.
- **`g0`:** `cagr(receita, 5)`, ou o do FCF se não houver receita, limitado a [0, `crescimento_max`].
- **Resultado:** valor por ação = VP / `acoes.valor`. É FCF alavancado com custo do capital próprio, sem ajuste de dívida.
- **Base do owner earnings:** lucro líquido do último ano + amortizações do último ano − média do capex de 3 anos.
- **Não aplicável:**
  - base ≤ 0 → motivo "FCF médio negativo" / "Owner earnings negativos";
  - `e_financeira` → "Não aplicável a bancos/seguradoras";
  - sem ações → "Sem número de ações".
- **Pressupostos devolvidos:** `g0`, `gT`, `r`, `base`, `anos_historico`.

- [ ] **Step 1: Testes que falham:**

```python
def test_vp_igual_gordon_quando_g_constante():
    # g0 = gT = 0.025, r = 0.08, base 100 → 100*1.025/0.055 = 1863.636...
    assert valor_presente(100, 0.025, 0.025, 0.08, 10) == pytest.approx(1863.636, rel=1e-4)
def test_dcf_por_acao():          # Empresa fake: FCF 100,100,100; 10 ações; receita estável; rf 0.025, beta 1 → r 0.08 → ≈ 186.36
def test_dcf_fcf_negativo():      # aplicavel False, motivo "FCF médio negativo"
def test_dcf_banco():             # e_financeira → aplicavel False
def test_taxa_desconto_minima():  # rf 0.01, beta 0.5 → 0.08
```

Cria um construtor de `Empresa` para testes em `tests/conftest.py`: `fazer_empresa(**campos)`, com séries anuais simples. Fica reutilizado nas tarefas seguintes.

- [ ] **Step 2: Correr e confirmar que falha.**
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Correr e confirmar que passa.**
- [ ] **Step 5: Commit.** `git commit -m "feat: two-stage DCF and owner earnings"`

---

### Task 7: Restantes métodos e valor central

**Files:**
- Create: `analise/valor/outros.py`, `analise/valor/central.py`, `tests/test_valor_outros.py`

**Interfaces:**
- Consumes: Tarefa 6 (`taxa_desconto`), `indicadores`.
- Produces:
  - `formula_graham(e) -> ResultadoMetodo`: `EPS × (8.5 + 2g) × 4.4 / Y`.
    - `g` em %: CAGR do EPS (ou da receita), limitado a [0, `g_max`].
    - `Y = (rf + spread_aaa) × 100`.
    - EPS ≤ 0 → não aplicável.
  - `numero_graham(e)`: `√(22.5 × EPS × BVPS)`, com BVPS = capital próprio / ações. EPS ou BVPS ≤ 0 → não aplicável.
  - `epv(e)`: (média do EBIT de até 5 anos × (1 − `taxa_imposto`) / r + caixa − dívida) / ações. Financeira → não aplicável.
  - `pe_historico(e)` e `ev_ebit_historico(e)`:
    - múltiplo de cada ano = preço de fecho no último dia útil do ano / EPS (ou EV / EBIT);
    - mediana sobre os anos com múltiplo > 0;
    - < `anos_minimos` → não aplicável;
    - valor = mediana × métrica atual (EV/EBIT: − dívida líquida, ÷ ações).
  - `gordon(e)`: só se houver dividendos em ≥ `anos_minimos` anos seguidos sem corte > 25 %.
    - `g = min(cagr dividendos, r − 0.01)`;
    - valor = `DPS × (1+g) / (r − g)`.
  - `pb_bancos(e)`: só se `e_financeira`; `ROE médio / r × BVPS`.
  - `todos_os_metodos(e) -> list[ResultadoMetodo]`.
  - `ValorCentral(central: float | None, minimo: float | None, maximo: float | None, margem: float | None, n_metodos: int)`.
  - `valor_central(metodos: list[ResultadoMetodo], preco: float) -> ValorCentral`: mediana dos aplicáveis, com margem `(V − P) / V`.

- [ ] **Step 1: Testes que falham:**

```python
def test_formula_graham():   # EPS 5, g 10 %, rf 0.034 (Y 4.4) → 142.5
def test_numero_graham():    # EPS 4, BVPS 25 → 47.434
def test_numero_graham_eps_negativo():  # aplicavel False, sem exceção
def test_epv():              # EBIT 100, t 0.25, r 0.08, caixa 100, dívida 200, 10 ações → 83.75
def test_gordon_corte():     # dividendos 1.0, 1.0, 0.5 → aplicavel False
def test_valor_central():    # valores 80, 100, 130 + 1 não aplicável, preço 85 → central 100, margem 0.15, n 3
def test_valor_central_vazio():  # nenhum aplicável → central None
```

- [ ] **Step 2: Correr e confirmar que falha.**
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Correr e confirmar que passa.**
- [ ] **Step 5: Commit.** `git commit -m "feat: Graham, EPV, multiples, Gordon, bank P/B and central value"`

---

### Task 8: Perfil (crescimento/valor e risco) e pontuação

**Files:**
- Create: `analise/perfil.py`, `analise/pontuacao.py`, `tests/test_perfil.py`, `tests/test_pontuacao.py`

**Interfaces:**
- Consumes: `indicadores`, `ValorCentral`, `config`.
- Produces:
  - `classificar(e, preco: float) -> tuple[str, list[str]]`: devolve "Crescimento", "Valor" ou "Misto", mais as razões com números. Regras do spec §12 com os limites em `[perfil]`.
  - `Alerta(nome: str, valor: str, limite: str)`, dataclass.
  - `alertas(e) -> list[Alerta]`: os 7 alertas de `[alertas]` mais "Moeda ≠ EUR (risco cambial)", que só é informativo e **não conta** para a etiqueta.
  - `etiqueta_risco(alertas: list[Alerta]) -> str`: conta só os 7 alertas configurados. 0–1 → "Baixo", 2–3 → "Médio", ≥ 4 → "Alto".
  - `calcular_pontuacao(e, vc: ValorCentral) -> Pontuacao`:
    - **Componentes e sub-indicadores**, exatamente como em `[pontuacao.limites]`:
      - valorizacao = [margem_seguranca];
      - qualidade = [roic médio, cv_margem_operacional, anos_receita_a_crescer];
      - solidez = [divida_liquida_ebitda, cobertura_juros, altman_z, piotroski_f];
      - risco_mercado = [beta, volatilidade, queda_maxima];
      - tendencia = [preco_vs_mm200, momento_12_1].
    - Nota do componente = média dos sub-indicadores não `None`. Sem nenhum, a nota é `None`.
    - Total = Σ peso × nota / Σ peso dos componentes com nota.
    - Cobertura = Σ peso dos componentes com nota.
    - Faixa: "Boa" se total ≥ 78 **e** cobertura ≥ 0.60; "Neutra" se total ≥ 60; senão "Fraca". `dados_insuficientes = cobertura < 0.60`.
    - Total `None` → faixa "Sem dados".

- [ ] **Step 1: Testes que falham:**

```python
def test_etiqueta_risco():          # 0→Baixo, 1→Baixo, 2→Médio, 4→Alto; alerta cambial não conta
def test_classificar_crescimento(): # CAGR receita 20% → "Crescimento"
def test_classificar_valor():       # P/E 10 → "Valor"
def test_pontuacao_pesos():         # notas fixas 100,80,60,40,20 → total 0.3*100+0.25*80+0.2*60+0.15*40+0.1*20 = 70.0
def test_pontuacao_redistribui():   # risco_mercado e tendencia None → total = (0.3*100+0.25*80+0.2*60)/0.75; cobertura 0.75
def test_sem_boa_com_pouca_cobertura():  # só valorizacao=100 (cob 0.30) → faixa != "Boa", dados_insuficientes True
def test_boa_78():                  # total 78, cobertura 1 → "Boa"; 77.9 → "Neutra"
```

Para testar a agregação sem empresas reais, expõe também `agregar(notas: dict[str, float | None]) -> Pontuacao`, usada internamente por `calcular_pontuacao`.

- [ ] **Step 2: Correr e confirmar que falha.**
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Correr e confirmar que passa.**
- [ ] **Step 5: Commit.** `git commit -m "feat: growth/value profile, risk label and 0-100 score"`

---

### Task 9: Lentes de investidores

**Files:**
- Create: `analise/lentes/__init__.py` e os seis módulos, `tests/test_lentes.py`

**Interfaces:**
- Consumes: `indicadores`, `valor.dcf.owner_earnings`, `valor.outros.numero_graham`, `config`.
- Produces: em cada módulo, `avaliar(e: Empresa) -> ResultadoLente`, e `lentes.todas(e) -> list[ResultadoLente]`.

Os critérios são os do spec §10, com limites numa nova secção `[lentes.*]` de `config.toml`. Cada `Criterio.valor` mostra o número e o limite, por exemplo "ROE 18 % (≥ 15 %)".

| Lente | Critérios | `valor_justo` |
|---|---|---|
| Buffett | ROE médio ≥ 15 % e CV(ROE) ≤ 0.3; dívida total / lucro ≤ 4; CV margem operacional ≤ 0.2; lucro > 0 em todos os anos | owner earnings × 0.75 |
| Graham | capitalização ≥ 2 000 M EUR (via `cambio_eur`); current ratio ≥ 2; lucro > 0 todos os anos; dividendos todos os anos; P/E ≤ 15; P/E×P/B ≤ 22.5 | número de Graham |
| Lynch | PEG ≤ 1; dívida total / capital próprio ≤ 0.5; crescimento do EPS entre 10 e 25 % | EPS × g (g em %, limitado a 25) |
| Ackman | CV(receita) ≤ 0.15; margem FCF ≥ 10 %; dívida líquida / EBITDA ≤ 3; FCF yield ≥ 5 % | média FCF 3 anos / 0.05 / ações |
| Greenblatt | earnings yield EBIT/EV ≥ 8 %; ROC = EBIT/(ativo corrente − passivo corrente + imobilizado) ≥ 25 % | `None`; `nota` = média de escala(ey, 0.02, 0.12) e escala(roc, 0.05, 0.40) |
| Druckenmiller | preço > MM200; momento 6 meses > 0; momento 12 meses > 0; EPS último > média dos 3 anteriores | `None`; resumo "Sinal favorável" (≥ 3 ok), "neutro" (2) ou "desfavorável" (≤ 1) |

Qualquer critério sem dados fica com o estado `"nd"`, nunca `"falha"`.

- [ ] **Step 1: Testes que falham.** Um por lente com a empresa de `conftest` desenhada para passar tudo, mais `test_criterio_sem_dados_e_nd`.
- [ ] **Step 2: Correr e confirmar que falha.**
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Correr e confirmar que passa.**
- [ ] **Step 5: Commit.** `git commit -m "feat: six investor lenses"`

---

### Task 10: SEC EDGAR (histórico dos EUA)

**Files:**
- Create: `analise/fontes/sec.py`, `tests/fixtures/sec_aapl_companyfacts.json` (reduzido), `tests/fixtures/sec_tickers.json`, `tests/test_sec.py`

**Interfaces:**
- Produces:
  - `cik_de(ticker: str) -> str | None`: lê `https://www.sec.gov/files/company_tickers.json` e devolve o CIK com zeros até 10 dígitos.
  - `series_de_companyfacts(dados: dict, hoje: str, cik: str) -> dict[str, Serie]`: **pura**.
    - Só usa factos `form == "10-K"` com período anual (`fp == "FY"`); por ano fiscal, fica com o último arquivado.
    - Tags → campo, a primeira que existir:
      - receita: `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`, `SalesRevenueNet`;
      - lucro_liquido: `NetIncomeLoss`;
      - fluxo_operacional: `NetCashProvidedByUsedInOperatingActivities`;
      - capex: `PaymentsToAcquirePropertyPlantAndEquipment`;
      - eps: `EarningsPerShareDiluted`;
      - acoes_media: `WeightedAverageNumberOfDilutedSharesOutstanding`;
      - ebit: `OperatingIncomeLoss`;
      - capital_proprio: `StockholdersEquity`;
      - dividendos por ação: `CommonStockDividendsPerShareDeclared`.
    - `fcf` = fluxo operacional − capex.
    - `Fonte("SEC EDGAR (10-K)", hoje, f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K")`.
  - `enriquecer(e: Empresa, user_agent: str | None) -> Empresa`:
    - só para `bolsa` dos EUA (NMS, NYQ, NGM, NCM, ASE, PCX);
    - substitui as séries do Yahoo pelas da SEC quando a SEC tem mais anos;
    - sem `user_agent` → aviso "SEC não configurada";
    - falha de rede → aviso, Empresa inalterada.

- [ ] **Step 1: Testes que falham:** 10 anos de receita a partir da fixture; tag alternativa usada quando falta `Revenues`; 10-Q ignorados; `user_agent=None` → aviso e séries inalteradas.
- [ ] **Step 2: Correr e confirmar que falha.**
- [ ] **Step 3: Implementar.** Cabeçalho `User-Agent: <valor configurado>`, `timeout=15`.
- [ ] **Step 4: Correr e confirmar que passa.**
- [ ] **Step 5: Commit.** `git commit -m "feat: SEC EDGAR history for US stocks"`

---

### Task 11: ESEF (relatório oficial da UE) e verificação cruzada

**Files:**
- Create: `analise/fontes/esef.py`, `analise/verificacao.py`, `tests/fixtures/gleif_*.json`, `tests/fixtures/xbrl_*.json`, `tests/test_esef.py`

**Interfaces:**
- Produces:
  - `lei_de(nome: str) -> str | None`: GLEIF `https://api.gleif.org/api/v1/lei-records?filter[fulltext]={nome}&page[size]=1`.
  - `ultimo_relatorio(lei: str) -> tuple[Fonte, dict[str, float]] | None`. Via filings.xbrl.org, devolve:
    - o link do visualizador do relatório mais recente;
    - `{receita, lucro_liquido}`, lidos do `json_url` (xBRL-JSON) pelos conceitos `ifrs-full:Revenue` e `ifrs-full:ProfitLoss` do período anual mais recente.

    Antes de implementar, confirma o formato atual do endpoint com um pedido real e grava-o como fixture. O formato pode mudar (spec §7).
  - `verificar(e: Empresa, oficial: dict[str, float], fonte: Fonte) -> list[str]`: em `verificacao.py`, comum a SEC e ESEF. Para receita e lucro líquido do mesmo ano, se `|yahoo − oficial| / |oficial| > divergencia_max`, devolve o aviso "⚠️ Receita {ano}: Yahoo X vs relatório oficial Y (dif. Z %)".
  - `enriquecer(e: Empresa) -> Empresa`:
    - só para países da UE/EEE;
    - acrescenta a fonte a `e.links` e os avisos de `verificar`;
    - qualquer falha (sem LEI, sem `json_url`, rede) → aviso "Relatório oficial não encontrado" e continua.
- Modify: `sec.py`, `enriquecer`, que passa a chamar `verificar` com o último ano da SEC.

- [ ] **Step 1: Testes que falham:** `verificar` com divergência de 5 % → 1 aviso; com 1 % → 0; ESEF sem `json_url` → aviso e nenhuma exceção; parse do xBRL-JSON da fixture.
- [ ] **Step 2: Correr e confirmar que falha.**
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Correr e confirmar que passa.**
- [ ] **Step 5: Commit.** `git commit -m "feat: ESEF official report link and cross-check"`

---

### Task 12: Serviço e ficha completa no telemóvel

**Files:**
- Create: `analise/servico.py`, `tests/test_app.py`
- Modify: `app.py` (substitui a versão mínima), `.streamlit/config.toml`

**Interfaces:**
- Consumes: tudo o que está acima.
- Produces:
  - `Ficha(empresa, metodos: list[ResultadoMetodo], central: ValorCentral, lentes: list[ResultadoLente], pontuacao: Pontuacao, classificacao: tuple[str, list[str]], alertas: list[Alerta], risco: str)`, dataclass.
  - `analisar(ticker: str, user_agent: str | None) -> Ficha | None`: sequência carregar_empresa → sec.enriquecer → esef.enriquecer → métodos → central → perfil → pontuação → lentes.

Interface (`app.py`), na ordem do esboço do spec §8:
- `st.set_page_config(layout="centered")`.
- **Pesquisa:**
  - `st.text_input` → `pesquisar`;
  - 0 resultados → "Não encontrei esta ação. Experimenta o ticker (ex.: ASML.AS).";
  - mais de 1 → `st.radio` para escolher.
- **Cabeçalho:**
  - nome · ticker · bolsa · moeda;
  - `st.metric` para preço, pontuação (com faixa) e risco;
  - valor central, intervalo e margem;
  - EUR ao lado se a moeda ≠ EUR.
- **Secções (`st.expander`):**
  - Sobre a empresa;
  - Crescimento ou valor;
  - Riscos;
  - Valor intrínseco (tabela: método, valor, aplicável/motivo, pressupostos);
  - Lentes (com o aviso fixo);
  - Pontuação (componentes, pesos, cobertura);
  - Fontes (`e.links` + fontes das séries + `e.avisos`).
- Rodapé com o aviso de não-aconselhamento.
- `@st.cache_data(ttl=43200)` em `pesquisar` e `analisar`.
- `user_agent` a partir de `st.secrets.get("SEC_USER_AGENT")` ou `os.environ`.
- Números formatados no padrão pt-PT: `1 234,56 €`, percentagens `15,0 %`. Uma função `formatar_numero` em `app.py`, testada.

- [ ] **Step 1: Testes que falham:**

```python
def test_formatar_numero():    # 1234.5, "EUR" → "1 234,50 €"
def test_app_sem_resultados(): # streamlit.testing.v1.AppTest com pesquisar monkeypatched → [] → texto "Não encontrei esta ação"
def test_app_ficha():          # analisar monkeypatched com Ficha fixa → aparecem "Pontuação", "Valor intrínseco", aviso de rodapé
```

- [ ] **Step 2: Correr e confirmar que falha.**
- [ ] **Step 3: Implementar `servico.py` e `app.py`.**
- [ ] **Step 4: Correr e confirmar que passa.** Run: `uv run pytest -q` → todos passam.
- [ ] **Step 5: Verificação manual.** Correr `uv run streamlit run app.py` e testar `ASML.AS`, `JMT.LS`, `AAPL`, `SHEL.L`, `SAN.MC` (banco), mais um ticker inexistente.
  - Expected: fichas sem erros; o banco marca os métodos FCF como não aplicáveis; o ticker inexistente mostra a mensagem.
  - Testar também no browser em largura de telemóvel (cerca de 400 px).
- [ ] **Step 6: Commit e publicar.** `uv export --no-hashes --no-dev -o requirements.txt; git add -A; git commit -m "feat: full stock card UI"; git push`. A Streamlit Cloud atualiza sozinha. O Sergio adiciona `SEC_USER_AGENT` nos Secrets da app, com o contacto dele.

---

### Task 13: README para o Sergio

**Files:** Create/Modify: `README.md`

- [ ] **Step 1: Escrever o README em português.** Inclui:
  - o que a app faz;
  - como correr localmente (`uv run streamlit run app.py`);
  - como correr os testes;
  - onde mudar limites e pesos (`config.toml`);
  - mapa das pastas (uma linha cada);
  - fontes e as suas limitações;
  - o aviso de não-aconselhamento.
- [ ] **Step 2: Commit.** `git commit -m "docs: README"`
