# 🐦 Bem-te-vi

> Seu assistente de inteligência de notícias. Lê suas newsletters do Gmail e feeds RSS, analisa com IA, e te manda um resumo diário no Telegram.

O bem-te-vi é um passarinho brasileiro cujo nome quer dizer literalmente *"bem te vi"* — e é isso que ele faz: vê as notícias por você e te conta o que importa.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
[![CI](https://github.com/Eduardozsw/Bem-te-vi/actions/workflows/ci.yml/badge.svg)](https://github.com/Eduardozsw/Bem-te-vi/actions/workflows/ci.yml)

## ✨ Funcionalidades

- 📥 Coleta de newsletters do Gmail (por marcador) + feeds RSS
- 🧠 Análise e pontuação de relevância com IA
- 🔗 Deduplicação semântica (a mesma notícia de várias fontes vira um item só)
- 📱 Relatório diário enxuto no Telegram: só os melhores itens, com link para a fonte
- ☁️ Roda de graça no GitHub Actions (agendado)
- 🔌 IA na **nuvem** (OpenAI, Anthropic, OpenRouter…) ou **local** (Ollama e afins) — sua escolha
- 🔁 Retries com backoff e timeout nas chamadas de IA; falhas parciais aparecem no relatório
- 📊 Registro de cada execução em SQLite (status, volumes, lotes com falha, tokens, custo)
- 👤 Perfil opcional: marca **qual projeto/ativo seu** cada notícia afeta

## 🔍 Como funciona

```
Gmail + RSS  →  deduplicação  →  análise (IA)  →  relatório no Telegram
```

O processamento de notícias não guarda estado entre rodadas. O único estado persistido é o
registro de execuções (`runs`), usado para monitoramento — veja [📊 Monitoramento](#-monitoramento).

## 🚀 Início rápido

```bash
git clone https://github.com/Eduardozsw/Bem-te-vi.git
cd Bem-te-vi
pip install -r requirements.txt
cp .env.example .env   # preencha suas chaves
python main.py
```

## ⚙️ Configuração (`.env`)

| Variável | Obrigatória | Descrição |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | sim | Token do bot (via @BotFather) |
| `TELEGRAM_CHAT_ID` | sim | Seu chat id no Telegram |
| `GMAIL_LABEL` | não | Marcador lido no Gmail (default: `newsletters`) |
| `LLM_MODEL` | não | Modelo no formato LiteLLM (default: `gpt-4o-mini`) |
| `LLM_API_KEY` | se usar nuvem | Chave do provedor de IA (OpenAI, Anthropic, OpenRouter…) |
| `LLM_API_BASE` | só local | Endpoint do provedor local (ex: `http://localhost:11434`) |
| `USER_PROFILE` | não | Perfil em YAML (uso como secret no Actions; local use `profile.yaml`) |
| `LLM_NUM_RETRIES` | não | Tentativas extras em erros transitórios da IA (default: `3`) |
| `LLM_TIMEOUT` | não | Timeout por chamada à IA, em segundos (default: `60`) |
| `RUNS_DB` | não | Caminho do SQLite com o registro de execuções (default: `data/runs.db`) |
| `REPORT_MIN_RELEVANCE` | não | Nota mínima (0–10) para um item entrar no relatório (default: `7`) |
| `REPORT_MAX_HIGHLIGHTS` | não | Quantos itens aparecem com análise completa (default: `5`) |

## 📱 O relatório

- Os itens com nota ≥ `REPORT_MIN_RELEVANCE` são ordenados pela nota. Os `REPORT_MAX_HIGHLIGHTS`
  primeiros saem com a análise completa (resumo, por que importa, impactos, ações).
- Os demais itens relevantes aparecem em **➕ Também relevantes**, uma linha cada (até 10).
- O que ficou abaixo do corte só é **contado** no cabeçalho, sem lista.
- Todo título é um link: o artigo, para RSS; a mensagem no Gmail, para newsletters (abre na
  primeira conta logada no navegador, `u/0`).
- Em dia sem nada relevante, o relatório diz isso numa linha em vez de encher a mensagem.

## 🧠 Escolha do modelo

Usa [LiteLLM](https://docs.litellm.ai/) — qualquer provedor suportado por ele
funciona (OpenAI, Anthropic, OpenRouter, Gemini, Ollama local…). É só apontar
`LLM_MODEL` para a string certa e dar a chave em `LLM_API_KEY`.

**Nuvem — default `gpt-4o-mini` (OpenAI), bom custo-benefício:**
```
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
```

**Nuvem — Anthropic (alternativa):**
```
LLM_MODEL=claude-haiku-4-5-20251001
LLM_API_KEY=sk-ant-...
```

**Local (Ollama) — grátis, sem chave de API:**
```bash
# 1. instale o Ollama: https://ollama.com
# 2. baixe um modelo
ollama pull qwen2.5:7b
```
```
LLM_MODEL=ollama/qwen2.5:7b
LLM_API_BASE=http://localhost:11434
```

## 👤 Perfil personalizado (opcional)

Por padrão a análise é genérica. Se você contar ao bot sobre seus projetos e
investimentos, ele passa a marcar **quais deles cada notícia afeta**
(`🏷️ Afeta: …`) e escreve o "por que importa" e as ações sob a sua ótica.

> ⚠️ **A personalização só acontece com o perfil definido.** Sem `profile.yaml`
> (local) ou o secret `USER_PROFILE` (no Actions), o bot roda normalmente, mas
> **sem as tags `🏷️ Afeta` e sem as ações sob medida** — a análise fica genérica.
> Quer o relatório personalizado? O perfil é obrigatório.

O perfil é um **dicionário aninhado livre** — cada projeto/ativo é uma entrada
nomeada com os campos que você quiser. O nome da entrada é o que aparece na tag.

```yaml
# profile.yaml
projetos:
  MeuApp:
    descricao: "o que o projeto faz"
    stack: "tecnologias relevantes, ex: depende de LLMs locais"
    o_que_me_importa: "custo de inferência, modelos pequenos bons"
investimentos:
  renda_fixa:
    posicoes: "CDB de liquidez diária, RDB"
    o_que_me_importa: "Selic, CDI, IPCA — afetam o rendimento"
```

Aí uma notícia relevante chega assim:

```
🔴 [8/10] Novo modelo Qwen 3B supera Llama 8B
🏷️ Afeta: MeuApp
📌 Fonte: Hacker News

Por que importa: roda no seu hardware atual com menos VRAM.
Ações possíveis:
• Testar qwen3:3b no MeuApp
```

**Local:** copie `profile.example.yaml` para `profile.yaml` e edite. O arquivo é
ignorado pelo Git — seus dados ficam só na sua máquina.

**No GitHub Actions:** cole o conteúdo do perfil no secret `USER_PROFILE`.

Sem perfil (arquivo ausente e secret vazio), nada muda — a análise segue
genérica, idêntica ao comportamento sem essa funcionalidade.

## 💻 Hardware

Escolha o modelo conforme sua máquina:

| Hardware | `LLM_MODEL` | `LLM_API_BASE` | Nota |
|---|---|---|---|
| Nuvem (qualquer máquina) | `gpt-4o-mini` *(default)* ou `claude-haiku-4-5-20251001` | — | precisa `LLM_API_KEY` |
| CPU apenas | `ollama/qwen2.5:3b` | `http://localhost:11434` | funciona, lento |
| GPU 6–8 GB | `ollama/qwen2.5:7b` | `http://localhost:11434` | recomendado p/ maioria |
| GPU 12–16 GB | `ollama/qwen2.5:14b` | `http://localhost:11434` | melhor qualidade |
| GPU 24 GB+ | `ollama/qwen2.5:32b` | `http://localhost:11434` | mais perto da nuvem |

## 📧 Setup do Gmail

1. No [Google Cloud Console](https://console.cloud.google.com/), crie um projeto e **ative a Gmail API**.
2. Configure a tela de consentimento OAuth (tipo *External*, modo *Testing*) e adicione seu email como *test user*.
3. Crie uma credencial *OAuth client ID* do tipo **Desktop app**, baixe o JSON e salve como `credentials.json` na raiz.
4. No Gmail, crie o marcador `newsletters` e um filtro que aplique esse marcador às newsletters desejadas.
5. Gere o token de acesso:
   ```bash
   python setup_gmail_auth.py
   ```
   Isso abre o navegador, você autoriza, e um `token.json` é criado. O app pede apenas acesso **somente leitura**.

## 💬 Setup do Telegram

1. Fale com o [@BotFather](https://t.me/BotFather), mande `/newbot` e siga os passos → você recebe o `TELEGRAM_BOT_TOKEN`.
2. Envie qualquer mensagem ao seu bot (obrigatório para ele poder te responder).
3. Descubra seu `TELEGRAM_CHAT_ID` falando com o [@userinfobot](https://t.me/userinfobot).

## 🤖 Rodando no GitHub Actions

O workflow `.github/workflows/daily.yml` roda diariamente (10h17 UTC). Configure os *secrets* do repositório:

- `LLM_API_KEY` (chave do seu provedor de IA — OpenAI, Anthropic…)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GMAIL_TOKEN_JSON` (conteúdo do `token.json` gerado localmente)
- `USER_PROFILE` (opcional — conteúdo do seu `profile.yaml` para análise personalizada)

O `credentials.json` **não** é necessário no Actions: o `token.json` já carrega o client id/secret
usados para renovar o acesso. Se você configurou um secret `GMAIL_CREDENTIALS_JSON` em versões
antigas, pode apagá-lo.

> ⚠️ Em repositórios públicos, o GitHub **desativa workflows agendados após 60 dias sem atividade**
> no repositório. Se o relatório parar de chegar, veja a aba *Actions* e reative o workflow
> (`gh workflow enable daily.yml`).

O workflow `.github/workflows/ci.yml` roda os testes em todo push e pull request (sem secrets —
todas as chamadas externas são mockadas).

## 📊 Monitoramento

**No relatório:** falhas parciais (feed fora do ar, deduplicação que falhou, lote de análise que
falhou) aparecem no rodapé ⚠️ da mensagem — ex.: `Análise: 1 de 3 lotes falharam (10 artigos não
analisados)`. Um crash do pipeline dispara um alerta 🚨 no Telegram e encerra com código 1.

**Registro de execuções:** cada execução grava uma linha na tabela `runs` de um SQLite
(schema escrito à mão em [`sql/schema.sql`](sql/schema.sql)):

| Coluna | Conteúdo |
|---|---|
| `started_at` / `finished_at` | início e fim (UTC, ISO 8601) |
| `status` | `success`, `partial` (houve avisos ou lotes com falha) ou `failed` (crash ou entrega falhou) |
| `articles_collected` / `articles_after_dedup` | volume antes e depois da deduplicação |
| `batches_total` / `batches_failed` | lotes enviados à IA e quantos falharam |
| `prompt_tokens` / `completion_tokens` / `cost_usd` | uso e custo estimado pelo LiteLLM |
| `model`, `warnings` (JSON), `error` | contexto para diagnóstico |

No Actions, o `runs.db` é versionado na branch **`data`** (um commit por execução) e também sobe
como artefato da execução. Para ver as métricas:

```bash
git fetch origin data && git show origin/data:runs.db > runs.db
sqlite3 runs.db < sql/queries.sql
```

[`sql/queries.sql`](sql/queries.sql) traz N de execuções, taxa de sucesso, % de lotes com falha,
redução da deduplicação, custo e duração média.

**Limitações conhecidas:**
- O retry é feito pelo LiteLLM (`num_retries`) e só cobre erros transitórios (timeout, conexão,
  5xx, rate limit). Os testes verificam que os parâmetros são passados, não o comportamento
  interno do LiteLLM.
- `cost_usd` é uma estimativa pela tabela de preços do LiteLLM; fica `NULL` quando o modelo não
  tem preço conhecido (ex.: modelos locais) — nunca é gravado como 0.
- O histórico começa na primeira execução com esta versão; rodadas anteriores não foram registradas.

## 🤝 Contribuindo

PRs e issues são bem-vindos. Rode os testes antes de abrir um PR:
```bash
python -m pytest
```

## 📄 Licença

MIT.
