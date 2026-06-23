# 🐦 Bem-te-vi

> Seu assistente de inteligência de notícias. Lê suas newsletters do Gmail e feeds RSS, analisa com IA, e te manda um resumo diário no Telegram.

O bem-te-vi é um passarinho brasileiro cujo nome quer dizer literalmente *"bem te vi"* — e é isso que ele faz: vê as notícias por você e te conta o que importa.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## ✨ Funcionalidades

- 📥 Coleta de newsletters do Gmail (por marcador) + feeds RSS
- 🧠 Análise e pontuação de relevância com IA
- 🔗 Deduplicação semântica (a mesma notícia de várias fontes vira um item só)
- 📱 Relatório diário formatado no Telegram
- ☁️ Roda de graça no GitHub Actions (agendado)
- 🔌 IA na **nuvem** (Anthropic) ou **local** (Ollama e afins) — sua escolha

## 🔍 Como funciona

```
Gmail + RSS  →  deduplicação  →  análise (IA)  →  relatório no Telegram
```

Cada execução é independente (stateless) — sem banco de dados, sem estado entre rodadas.

## 🚀 Início rápido

```bash
git clone https://github.com/Eduardozsw/news-intelligence-assistant.git
cd news-intelligence-assistant
pip install -r requirements.txt
cp .env.example .env   # preencha suas chaves
python main.py
```

## ⚙️ Configuração (`.env`)

| Variável | Obrigatória | Descrição |
|---|---|---|
| `ANTHROPIC_API_KEY` | se usar a nuvem | Chave da API da Anthropic |
| `TELEGRAM_BOT_TOKEN` | sim | Token do bot (via @BotFather) |
| `TELEGRAM_CHAT_ID` | sim | Seu chat id no Telegram |
| `GMAIL_LABEL` | não | Marcador lido no Gmail (default: `newsletters`) |
| `LLM_MODEL` | não | Modelo no formato LiteLLM (default: `claude-haiku-4-5-20251001`) |
| `LLM_API_BASE` | só local | Endpoint do provedor local (ex: `http://localhost:11434`) |
| `LLM_API_KEY` | depende | Chave para provedores que exigem (ex: OpenRouter) |
| `USER_PROFILE` | não | Perfil em YAML (uso como secret no Actions; local use `profile.yaml`) |

## 🧠 Escolha do modelo

**Nuvem (Anthropic) — default, zero setup local:**
```
ANTHROPIC_API_KEY=sk-ant-...
# LLM_MODEL já é o Haiku por padrão
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
investimentos, ele passa a marcar **quais deles cada notícia afeta** (`🏷️ Afeta: …`)
e escreve as ações sob a sua ótica.

**Local:** copie `profile.example.yaml` para `profile.yaml` e edite. O arquivo é
ignorado pelo Git — seus dados ficam só na sua máquina.

**No GitHub Actions:** cole o conteúdo do perfil no secret `USER_PROFILE`.

Sem perfil, nada muda — segue genérico.

## 💻 Hardware

Escolha o modelo conforme sua máquina:

| Hardware | `LLM_MODEL` | `LLM_API_BASE` | Nota |
|---|---|---|---|
| Nuvem (qualquer máquina) | `claude-haiku-4-5-20251001` *(default)* | — | precisa `ANTHROPIC_API_KEY` |
| CPU apenas | `ollama/qwen2.5:3b` | `http://localhost:11434` | funciona, lento |
| GPU 6–8 GB | `ollama/qwen2.5:7b` | `http://localhost:11434` | recomendado p/ maioria |
| GPU 12–16 GB | `ollama/qwen2.5:14b` | `http://localhost:11434` | melhor qualidade |
| GPU 24 GB+ | `ollama/qwen2.5:32b` | `http://localhost:11434` | mais perto do Haiku |

Como usa LiteLLM, qualquer provedor suportado por ele funciona (OpenAI, OpenRouter, Gemini, etc.) — basta a string certa em `LLM_MODEL`.

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

O workflow `.github/workflows/daily.yml` roda diariamente. Configure os *secrets* do repositório:

- `ANTHROPIC_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GMAIL_TOKEN_JSON` (conteúdo do `token.json` gerado localmente)

## 🤝 Contribuindo

PRs e issues são bem-vindos. Rode os testes antes de abrir um PR:
```bash
python -m pytest
```

## 📄 Licença

MIT.
