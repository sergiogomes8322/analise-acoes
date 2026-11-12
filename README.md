# Análise de Ações

Aplicação web (feita em Python com Streamlit) para analisar ações cotadas.

Escreves o nome ou o símbolo (o *ticker*, por exemplo `AAPL`) de uma empresa e a app mostra uma ficha com:

- **Análise**: indicadores da empresa, como rentabilidade, dívida e crescimento.
- **Valor intrínseco**: quanto a empresa deveria valer, calculado por vários métodos (DCF, Owner Earnings, fórmula e número de Graham, EPV, múltiplos históricos, Gordon, P/B para bancos). *DCF* quer dizer fluxos de caixa descontados: estima o dinheiro que a empresa vai gerar e traz esse valor para hoje.
- **Lentes de 6 investidores**: Buffett, Graham, Lynch, Ackman, Greenblatt e Druckenmiller. Cada lente aplica os critérios conhecidos desse investidor.
- **Pontuação de 0 a 100**, com o risco incluído. A partir de **78** a nota é "Boa".

> Informação educativa, não é aconselhamento financeiro.
> As lentes são interpretações feitas por este programa, não são opiniões dos investidores.
> O limite de 78 é uma regra tua, não é uma previsão de que a ação vai subir.

## Correr localmente

```
uv run python -m streamlit run app.py
```

Usa `python -m streamlit` e não `uv run streamlit`: no Windows, o segundo pode falhar com "Acesso negado".

## Testes

```
uv run pytest -q
```

Os testes funcionam sem internet. Usam dados de exemplo guardados em vez de ir buscar dados reais.

## Onde mudar limites e pesos

Tudo está no `config.toml` da raiz do projeto (não o de `.streamlit/`). Podes editar os números sem mexer no código. As secções principais:

- `[pontuacao.pesos]`: quanto cada parte conta na nota (valorização, qualidade, solidez, risco de mercado, tendência). Somam 1.
- `[pontuacao.faixas]`: a nota a partir da qual é "Boa" (`boa = 78`), "Neutra" (`neutra = 60`) e a cobertura mínima de dados.
- `[pontuacao.limites]`: para cada indicador, o valor que dá 0 pontos e o que dá 100.
- `[alertas]`: valores que fazem aparecer um aviso (volatilidade, dívida, beta, lucros concentrados num ano, possível ADR, etc.).
- `[lentes.*]`: critérios de cada investidor, por exemplo `[lentes.buffett]` ou `[lentes.graham]`.
- `[dcf]`: prémio de mercado, crescimento terminal, número de anos, etc.
- `[sem_risco_defeito]`: taxa sem risco por moeda, usada quando não há taxa atual. Tem uma data (`data = "2026-11-11"`) e deve ser **revista** de tempos a tempos.

Há ainda `[graham]`, `[impostos]`, `[historico]`, `[perfil]` (limites das etiquetas do perfil, p.ex. o que conta como penny stock ou grande empresa) e `[verificacao]`.

## Mapa das pastas

- `app.py`: a interface (o ecrã que vês no browser).
- `config.toml`: limites, pesos e taxas da análise (ver acima).
- `analise/`: toda a lógica, sem interface.
  - `config.py`: lê o `config.toml`.
  - `modelo.py`: as estruturas de dados (empresa, resultados).
  - `indicadores.py`: calcula os indicadores financeiros.
  - `fontes/`: vai buscar dados (`yahoo.py`, `taxas.py`, `sec.py`, `esef.py`).
  - `valor/`: métodos de valor intrínseco (`dcf.py`, `outros.py`) e o valor central (`central.py`).
  - `perfil.py`: perfil da empresa (estilo, dimensão, blue chip, penny stock, categoria Peter Lynch, setor, dividendos) e alertas de risco.
  - `pontuacao.py`: calcula a nota de 0 a 100.
  - `lentes/`: uma lente por investidor.
  - `servico.py`: junta tudo para a app usar.
  - `verificacao.py`: compara dados de fontes diferentes e avisa se divergem.
- `tests/`: testes automáticos.
- `.streamlit/`: `config.toml` com as definições do Streamlit (não tem limites da análise); `secrets.toml` é só local e nunca vai para o Git.
- `docs/`: especificação e planos do projeto.
- `requirements.txt`: dependências para o Streamlit Cloud (gerado, ver abaixo).
- `pyproject.toml` e `uv.lock`: dependências do projeto, geridas pelo `uv`.

## Fontes de dados e limites

- **Yahoo Finance**: preços e dados financeiros. Não é uma fonte oficial: pode falhar ou mudar sem aviso.
- **SEC EDGAR** (empresas dos EUA): relatórios oficiais. Exige que o pedido se identifique com um contacto, na variável `SEC_USER_AGENT`. Define-a nos *Secrets* do Streamlit Cloud ou como variável de ambiente. Nunca a ponhas no Git.
- **filings.xbrl.org + GLEIF** (empresas da Europa): relatórios oficiais ESEF. O índice nem sempre encontra a empresa, por isso funciona "o melhor possível".
- **BCE** (Banco Central Europeu): a taxa sem risco do EUR e os câmbios. A taxa do USD vem do Yahoo (`^TNX`). As outras moedas usam os valores por defeito do `config.toml`.
- **TradingView não é usado**: os termos de utilização proíbem a recolha automática de dados.

## Segredos

Para correr localmente, cria `.streamlit/secrets.toml` (o Git ignora este ficheiro):

```toml
SEC_USER_AGENT = "Nome contacto@exemplo.com"
```

Troca o texto por um nome e um contacto teus. Não partilhes este ficheiro.

## Publicar (mais tarde)

1. `gh auth login` para entrares no GitHub.
2. Cria um repositório **privado** no GitHub e envia o código.
3. Vai a share.streamlit.io, escolhe *New app* e indica `app.py`.
4. Em *Secrets*, adiciona `SEC_USER_AGENT = "Nome contacto@exemplo.com"`.

Se mudares dependências, regenera o `requirements.txt`:

```
uv export --no-hashes --no-dev -o requirements.txt
```

## Windows e antivírus (AVG)

Se aparecerem erros de HTTPS ao correr localmente (`CERTIFICATE_VERIFY_FAILED` ou "unable to get local issuer certificate"), o antivírus está a inspecionar as ligações HTTPS. Há duas soluções:

- **A**: desligar a análise de HTTPS no antivírus, ou excluir os sites de dados.
- **B**: criar um ficheiro de certificados (o pacote do `certifi` mais o certificado raiz do antivírus, exportado do Windows) e apontar para ele as variáveis de ambiente de utilizador `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE` e `CURL_CA_BUNDLE`.

Isto só é preciso no teu PC. O Streamlit Cloud não precisa.
