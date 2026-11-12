# Design: App de análise de ações (valor intrínseco, lentes de investidores, pontuação)

Data: 2026-11-11 · Estado: aprovado pelo Sergio

## 1. Intenção e porquê

O Sergio quer uma ferramenta pessoal para apoiar as suas decisões de investimento em ações. Também quer **aprender a programar** enquanto ela é construída.

Escreve-se o nome ou o ticker de uma ação e a app devolve uma ficha com:
- breve análise da empresa;
- valor intrínseco calculado por vários métodos;
- "lentes" que mostram o que a ação valeria segundo os princípios de investidores conhecidos;
- uma pontuação de 0 a 100 que inclui o risco.

O conteúdo é o que importa; a interface pode ser básica. Tem de funcionar no telemóvel e custar **0 €**.

Cada número tem de mostrar a sua fonte, para poder ser confirmado ("verifica sempre as fontes").

## 2. Objetivos

1. **Pesquisa rápida:** um campo onde se escreve um nome ("ASML", "Jerónimo Martins") ou um ticker ("ASML.AS", "JMT.LS", "AAPL"). Se houver várias correspondências, o utilizador escolhe a certa.
2. **Cobertura:** ações das principais bolsas acessíveis a um investidor europeu. Isso inclui EUA (NYSE, Nasdaq) e Europa (Euronext Amesterdão, Paris, Lisboa e Bruxelas, Xetra, Londres, Madrid, Milão, Suíça e nórdicas). Inclui ainda as que o Yahoo Finance cobrir.
3. **Breve análise:**
   - o que a empresa faz;
   - setor e indústria;
   - país e moeda;
   - capitalização;
   - classificação **crescimento / valor / misto**;
   - principais riscos.
4. **Valor intrínseco** por vários métodos, cada um com o seu valor por ação, os pressupostos usados e se é aplicável. Mostra-se também um **valor central**, a mediana dos métodos aplicáveis, e o intervalo entre eles.
5. **Lentes de investidores:** para cada investidor, uma checklist dos seus critérios (cumpre / não cumpre / sem dados). Quando faz sentido, também um valor justo segundo a sua abordagem, por exemplo: "Valor central 100 €; segundo a lente Buffett, 84 €".
6. **Pontuação 0–100** com o risco incluído. **≥ 78 = "Boa"**. A pontuação vem decomposta por componentes, para se perceber de onde vem.
7. **Rastreabilidade:** cada valor mostra a fonte, a data e, quando existe, o link para o documento original.
8. **Telemóvel:** abre num link no browser do telemóvel, numa coluna só, legível sem zoom.
9. **Ensino (escolha do Sergio: ver construir, por agora).**
   - O Claude escreve o código.
   - Em cada passo explica na conversa o que fez e porquê: a arquitetura, a fonte de dados e a fórmula.
   - O código fica pequeno e organizado, comentado onde o "porquê" não é óbvio.
   - O Sergio não escreve código nesta fase; pode pedir para passar a escrever mais tarde.
   - Os passos são pequenos, para cada explicação caber numa leitura.

## 3. Não-objetivos (v1)

- Não compra nem vende nada. Não há ligação a corretoras.
- Não há screener de milhares de ações nem listas automáticas acima de 78 (é possível numa versão futura).
- Não há backtest histórico da pontuação, porque as fontes grátis dão poucos anos de balanços. Fica para o futuro.
- Não há contas de utilizador, carteiras, alertas nem notificações.
- Não há resumo escrito por IA. Poderá vir como extra opcional com o plano grátis do Google Gemini.
- Não há app nativa (Android/iOS).

## 4. Anti-objetivos (falharia mesmo que funcione)

- **Números sem fonte**, ou números inventados quando faltam dados. Quando falta um dado mostra-se "N/D" e o motivo; nunca se estima em silêncio.
- **Fazer passar as lentes pela opinião real dos investidores.** São interpretações de princípios públicos e a app di-lo claramente.
- **Apresentar a pontuação como recomendação ou garantia de retorno.** Aparece sempre um aviso de que isto não é aconselhamento financeiro.
- **Qualquer custo:** APIs pagas, ou um serviço grátis que passe a cobrar sem aviso.
- **Violar os termos de uso das fontes.** Por exemplo, não há scraping da TradingView, que o proíbe e bane contas.

## 5. Restrições

- **Custo 0 €.** A app é alojada na Streamlit Community Cloud (grátis). Adormece após alguns dias sem uso e demora cerca de 30 s a acordar, o que é aceitável.
- **Fontes grátis e legítimas** (ver secção 7). O Yahoo Finance não é uma API oficial e pode falhar ou mudar, por isso a app tem de lidar bem com falhas.
- **Linguagem:** Python, para o Sergio aprender uma só linguagem.
- **Interface em português de Portugal.** Os valores aparecem na moeda da ação; o equivalente em euros aparece ao lado quando a moeda for outra.
- **Tempo de resposta:** a ficha deve aparecer em menos de 15 s na primeira consulta. As seguintes vêm da cache.
- **Ambiente local:** Windows 10, Python gerido com `uv` (já instalado).

## 6. Abordagens consideradas

| | Abordagem | Prós | Contras |
|---|---|---|---|
| **A (escolhida)** | Streamlit (só Python), alojada na Streamlit Community Cloud | Uma linguagem; chega-se mais depressa ao conteúdo; abre no telemóvel por link | Aspeto simples; adormece quando não é usada |
| B | App web HTML/JS (PWA) + API Python grátis (ex.: Render) | Parece uma app nativa | Duas linguagens e duas partes; mais lenta a construir |
| C | Corre no PC; o telemóvel acede pela rede de casa | Sem alojamento | O PC tem de estar ligado; fora de casa é preciso configurar |

**Escolhida pelo Sergio: A**, por recomendação. Os cálculos ficam em módulos Python independentes da interface, por isso podem ser reaproveitados se um dia se mudar para B.

## 7. Fontes de dados

| Fonte | Para quê | Notas |
|---|---|---|
| **Yahoo Finance** via biblioteca `yfinance` | Pesquisa de nome→ticker, perfil (descrição, setor), cotações e histórico de preços, balanços anuais (~4 anos), dividendos, número de ações | Cobre quase todas as bolsas. Não é oficial e pode falhar. A descrição vem em inglês |
| **SEC EDGAR** (`companyfacts` API, grátis) | Empresas dos EUA: até 10+ anos de receitas, lucros, FCF e ações em circulação; link para o 10-K | Oficial. Exige um cabeçalho `User-Agent` com um contacto, que é configurável e não é codificado |
| **filings.xbrl.org** (índice ESEF, grátis) | Empresas da UE: link para o relatório anual oficial; verificação de receita e lucro | Oficial na origem; o índice é mantido sem garantias e o formato pode mudar |
| **BCE** (taxas de câmbio de referência, grátis) | Conversão para EUR | Oficial |
| **Taxa sem risco** | Usada no DCF | Rendimento das obrigações alemãs a 10 anos (Bund) ou dos EUA (^TNX no Yahoo), conforme a moeda. Há um valor por defeito configurável |

**Anos de histórico (decisão do Claude).**
- Nos EUA, a **SEC EDGAR é a fonte principal do histórico**, com 10 anos ou mais. O Yahoo fica para preços e perfil. A SEC entra cedo na construção.
- Fora dos EUA usam-se os anos que o Yahoo tiver, normalmente cerca de 4.
- Uma regra que peça "5 anos" usa os anos disponíveis e indica-o, por exemplo "média de 4 anos (pedidos 5)".
- Com menos de 3 anos a regra fica N/D.

**Taxa sem risco por moeda (decisão do Claude).**
- **EUR:** curva de rendimentos AAA da zona euro a 10 anos, da API grátis do BCE (Data Portal).
- **USD:** `^TNX` do Yahoo.
- **GBP/GBp, CHF, SEK, DKK, NOK e outras:** valor por defeito por moeda em `config.toml`, com a data em que foi definido e um aviso "taxa por defeito" na ficha.
- Se a fonte falhar, usa-se o valor por defeito e mostra-se o aviso.
- Cotações em GBp (pence) são convertidas para GBP antes de qualquer cálculo.

**Risco de bloqueio do Yahoo na nuvem (decisão do Claude).**
- O yfinance é muitas vezes limitado a partir de servidores partilhados. Por isso, **o primeiro passo da construção é um teste** na Streamlit Community Cloud: pesquisar 5 tickers de bolsas diferentes.
- Se falhar, passa-se a correr a app no PC (abordagem C) até haver alternativa. Os cálculos não mudam.
- Em qualquer caso, a cache de 12 h reduz os pedidos.

**Verificação cruzada:** quando há SEC ou ESEF para o último ano, compara-se a receita e o lucro líquido com o Yahoo. Uma diferença acima de 2 % mostra um aviso ⚠️ junto ao número.

**TradingView e MoneyFlix ficam excluídos como fontes.** A TradingView proíbe a recolha automática de dados. A MoneyFlix é um podcast, não uma base de dados. O Sergio pode usá-las à mão para confirmar.

## 8. Conteúdo da ficha (de cima para baixo, numa coluna)

```
[ 🔍  nome ou ticker              ]
ASML Holding N.V. · ASML.AS · Euronext Amsterdam · EUR
Preço 612,40 €    Pontuação 81/100  ● Boa    Risco: Médio
──────────────────────────────────────────────
Valor intrínseco (central)   705 €   intervalo 540–860 €
Margem de segurança          +15 %
──────────────────────────────────────────────
▸ Sobre a empresa      (descrição, setor, país, capitalização)
▸ Crescimento ou valor (classificação + porquê)
▸ Riscos               (lista com ●/●/●)
▸ Valor intrínseco     (tabela: método · valor · aplicável · pressupostos)
▸ Lentes               (Buffett · Graham · Lynch · Ackman · Greenblatt · Druckenmiller)
▸ Pontuação            (componentes e pesos)
▸ Fontes               (cada fonte, data, link; avisos de divergência)
Aviso: informação educativa, não é aconselhamento financeiro.
```

## 9. Métodos de valor intrínseco

Cada método devolve o valor por ação, os pressupostos e a indicação de se é aplicável e porquê.

1. **DCF a 2 fases sobre o Free Cash Flow:**
   - crescimento inicial = CAGR das receitas ou do FCF a 3–5 anos, limitado a 0–20 %;
   - converge linearmente durante 10 anos para o crescimento terminal (2,5 %);
   - taxa de desconto = taxa sem risco + prémio de mercado (5,5 %) × beta, com um mínimo de 8 %.
   - Não aplicável se o FCF médio for negativo.
2. **Owner earnings (Buffett):** lucro líquido + amortizações − capex de manutenção (aproximado pelo capex médio), descontado como no DCF.
3. **Fórmula de Graham:** `EPS × (8,5 + 2g) × 4,4 / Y`, em que `g` está limitado a 15 % e `Y` é o rendimento das obrigações AAA (por defeito, a taxa sem risco + 1 %).
4. **Número de Graham:** `√(22,5 × EPS × BVPS)`. Não aplicável se o EPS ou o BVPS forem ≤ 0.
5. **EPV, Earnings Power Value (Greenwald):** EBIT normalizado × (1 − imposto) / custo de capital, sem crescimento.
6. **Múltiplos:**
   - P/E atual comparado com a mediana do P/E da própria ação em 5 anos;
   - EV/EBIT comparado com a mesma mediana.
   - Usa histórico próprio, porque não há dados grátis fiáveis de pares do setor.
7. **Desconto de dividendos (Gordon):** só para empresas que pagam dividendos estáveis há 5 anos ou mais.

O **valor central** é a mediana dos métodos aplicáveis, e o **intervalo** vai do mínimo ao máximo.

**Bancos e seguradoras:** o FCF não tem significado nestes casos. Usa-se o P/B justo = ROE / custo de capital × BVPS e o número de Graham. A app marca a análise como "limitada".

## 10. Lentes de investidores

Cada lente é uma interpretação de princípios publicados. Mostra:
- uma checklist (✔ / ✘ / N/D) com os limites usados;
- um valor justo, quando a abordagem do investidor o permite;
- uma frase de resumo.

| Lente | Critérios (limites por defeito) | Valor justo |
|---|---|---|
| **Buffett** | ROE ≥ 15 % em média 5 anos e estável; dívida/lucro ≤ 3–4 anos; margens estáveis (proxy de vantagem competitiva); lucros previsíveis | Owner earnings com margem de segurança de 25 % |
| **Graham** (defensivo) | Dimensão; current ratio ≥ 2; lucros positivos todos os anos; dividendos; P/E ≤ 15; P/E×P/B ≤ 22,5 | Número de Graham |
| **Peter Lynch** | PEG ≤ 1; dívida baixa; crescimento do EPS 10–25 % | EPS × taxa de crescimento (P/E justo = g) |
| **Bill Ackman** | Negócio simples e previsível (variação de receitas baixa); FCF forte; balanço sólido; FCF yield | FCF normalizado × múltiplo justo (FCF yield alvo de 5 %) |
| **Greenblatt** (fórmula mágica) | Earnings yield (EBIT/EV) e retorno sobre capital elevados | Sem valor justo; dá uma nota |
| **Druckenmiller** | Abordagem macro e de tendência: preço acima da média móvel de 200 dias; momento a 6–12 meses; tendência do EPS | **Sem valor justo:** não é um investidor de valor intrínseco. A lente dá um sinal de "timing" |

Os limites ficam num único ficheiro de configuração legível, para o Sergio poder ajustá-los e aprender com isso.

## 11. Pontuação 0–100

A pontuação é a média ponderada de cinco componentes. Cada um vai de 0 a 100. O beta e o risco entram na pontuação, por escolha do Sergio.

| Componente | Peso | O que mede |
|---|---|---|
| Valorização | 30 % | Preço face aos múltiplos habituais da própria ação (mediana do P/E e do EV/EBIT históricos). Decisão do Sergio em 2026-11-12: o valor central ficava muito abaixo do preço nas empresas de qualidade e punha esta nota a 0 em quase todas |
| Qualidade | 25 % | ROIC/ROE, margens e a sua estabilidade, crescimento consistente |
| Solidez | 20 % | Dívida líquida/EBITDA, cobertura de juros, Altman Z, Piotroski F |
| Risco de mercado | 15 % | Beta, volatilidade a 1 ano, queda máxima a 5 anos. Menos risco dá mais pontos |
| Tendência | 10 % | Preço face à média de 200 dias, momento |

- **Faixas:** ≥ 78 Boa · 60–77 Neutra · < 60 Fraca.
- **Risco (Baixo / Médio / Alto):** é mostrado à parte. Calcula-se a partir de:
  - volatilidade a 1 ano;
  - queda máxima a 5 anos;
  - beta;
  - alavancagem;
  - FCF negativo;
  - diluição de ações.

  O risco também entra na pontuação, através da componente de solidez.
- **Dados em falta:** um componente sem dados não entra no cálculo e os pesos são redistribuídos. A app mostra a **cobertura**, por exemplo "pontuação baseada em 85 % dos dados". Com cobertura abaixo de 60 % não aparece a etiqueta "Boa".
- **Pesos:** ficam no ficheiro de configuração.
- **O que o 78 é:** uma regra definida pelo Sergio, não uma previsão.

**Conversão em 0–100 (decisão do Claude, ajustável em `config.toml`).**

Cada sub-indicador é convertido de forma linear entre um limite "0" e um limite "100", sem sair desse intervalo. O componente é a média dos sub-indicadores com dados.

| Componente | Sub-indicador | → 0 | → 100 |
|---|---|---|---|
| Valorização | Margem face ao histórico `(V − P) / V`, com V = mediana do P/E e do EV/EBIT históricos | ≤ −30 % | ≥ +30 % |
| Qualidade | ROIC (ou ROE em bancos), média dos anos disponíveis | ≤ 5 % | ≥ 25 % |
| Qualidade | Estabilidade da margem operacional (coeficiente de variação) | ≥ 0,5 | ≤ 0,1 |
| Qualidade | % dos anos com receita a crescer | 0 % | 100 % |
| Solidez | Dívida líquida / EBITDA | ≥ 4 | ≤ 0 |
| Solidez | Cobertura de juros (EBIT / juros) | ≤ 1,5 | ≥ 10 |
| Solidez | Altman Z | ≤ 1,8 | ≥ 3 |
| Solidez | Piotroski F | 0 | 9 |
| Risco de mercado | Beta | ≥ 1,8 | ≤ 0,8 |
| Risco de mercado | Volatilidade anualizada a 1 ano | ≥ 50 % | ≤ 20 % |
| Risco de mercado | Queda máxima a 5 anos | ≥ 65 % | ≤ 25 % |
| Tendência | Preço / média de 200 dias − 1 | ≤ −20 % | ≥ +20 % |
| Tendência | Retorno a 12 meses, sem o último mês | ≤ −30 % | ≥ +30 % |

Exemplo: chegar a 78 exige, ao mesmo tempo, boa qualidade, um preço abaixo do valor central e um balanço sólido. Uma empresa excelente mas cara fica, em regra, abaixo de 78. É intencional.

**Etiqueta de risco.** Conta-se quantos alertas estão ativos:
- volatilidade a 1 ano > 40 %;
- queda máxima a 5 anos > 50 %;
- beta > 1,5;
- dívida líquida / EBITDA > 3;
- FCF negativo;
- diluição > 3 %/ano;
- Altman Z < 1,8.

0–1 alertas = Baixo, 2–3 = Médio, ≥ 4 = Alto.

A etiqueta resume o risco de relance. Os mesmos indicadores também entram na pontuação, através dos componentes "Risco de mercado" e "Solidez".

## 12. Crescimento vs valor e riscos

- **Crescimento:**
  - CAGR das receitas a 3 anos ≥ 15 %;
  - **ou** P/E > 25 com crescimento ≥ 10 %.
- **Valor:**
  - P/E < 15;
  - **ou** P/B < 1,5 com dividendo.
- **Misto:** o resto.
- A classificação mostra sempre os números que a justificam.

**Riscos detetados por regras.** Cada um mostra o valor e o limite:
- dívida elevada;
- cobertura de juros < 3;
- FCF negativo;
- diluição > 3 %/ano;
- volatilidade alta;
- queda máxima > 50 %;
- Altman Z < 1,8;
- concentração num único ano de lucros;
- moeda diferente do EUR (risco cambial).

## 13. Estrutura do código (proposta)

```
app.py                  # interface Streamlit (só apresentação)
analise/
  fontes/               # yahoo.py, sec.py, esef.py, cambio.py — cada um devolve dados + origem
  modelo.py             # estrutura de dados da empresa (números + fonte de cada um)
  valor/                # dcf.py, graham.py, epv.py, multiplos.py, dividendos.py
  lentes/               # buffett.py, graham.py, lynch.py, ackman.py, greenblatt.py, druckenmiller.py
  pontuacao.py
  perfil.py             # crescimento/valor, riscos
config.toml             # limites, pesos, taxas por defeito
tests/                  # pytest com números fixos (sem internet)
```

- Os cálculos são funções puras: recebem números e devolvem um resultado. Isso torna-os fáceis de testar e de explicar.
- A cache é `st.cache_data` com 12 h de validade, para não sobrecarregar as fontes.
- A interface usa `layout="centered"` e secções expansíveis, adequadas ao telemóvel.

## 14. Deixado ao construtor

- Bibliotecas auxiliares (ex.: `requests`, `pandas`), detalhes do parsing do XBRL e organização interna dos módulos.
- Escolha dos tickers dos testes e dos números de exemplo.
- Detalhe visual dentro do esboço da secção 8.
- Ordem de construção. Sugestão: primeiro a ficha com Yahoo + DCF + Graham, depois as restantes fontes, lentes e pontuação. Assim o Sergio vê resultados cedo.
- Publicação: repositório GitHub ligado à Streamlit Community Cloud. O Sergio faz o login (GitHub e Streamlit), porque são contas dele.
