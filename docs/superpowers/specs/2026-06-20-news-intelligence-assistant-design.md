# Design: News Intelligence Assistant

**Data:** 2026-06-20  
**Status:** Aprovado

## Objetivo

Sistema pessoal de uso diário que consome newsletters (Gmail) e RSS feeds, filtra ruído com Claude (Haiku), e entrega um único relatório no Telegram com apenas o que merece atenção real.

O objetivo **não** é resumir tudo — é filtrar e destacar informações com impacto real.

---

## Arquitetura

Pipeline linear simples em Python, sem estado persistente entre execuções. GitHub Actions roda o pipeline completo uma vez por dia.

```
Gmail (label) ──┐
                ├──► [coleta] ──► List[Article] ──► [analyzer] ──► List[AnalysisResult] ──► [telegram]
RSS feeds ──────┘
```

---

## Estrutura de Arquivos

```
news-intelligence-assistant/
├── main.py                        # entrypoint, orquestra o pipeline
├── setup_gmail_auth.py            # script de setup inicial (roda localmente uma vez)
├── config.yaml                    # lista de RSS feeds
├── .env                           # ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
├── .env.example
├── requirements.txt
├── .github/
│   └── workflows/
│       └── daily.yml              # roda às 10h UTC (7h BRT) todo dia
└── src/
    ├── gmail_reader.py            # autenticação OAuth + leitura por label
    ├── rss_reader.py              # leitura de feeds do config.yaml
    ├── analyzer.py                # batching + chamada ao Claude Haiku
    ├── telegram_sender.py         # formata e envia relatório
    └── models.py                  # dataclasses: Article, AnalysisResult
```

---

## Módulos

### `models.py`

Dataclasses compartilhadas entre todos os módulos:

```python
@dataclass
class Article:
    source: str
    title: str
    content: str
    url: str
    published_at: datetime

@dataclass
class AnalysisResult:
    title: str
    source: str
    url: str
    relevance: int          # 0-10
    summary: str
    why_it_matters: str
    impacts: list[str]
    actions: list[str]
```

### `gmail_reader.py`

- Autentica via OAuth 2.0 usando `google-auth` e `google-api-python-client`
- Em produção (Actions), reconstrói `credentials.json` e `token.json` a partir de secrets do GitHub
- Busca emails com a label configurada recebidos nas últimas 24h
- Extrai corpo em `text/plain` (preferido) ou `text/html` com strip de tags como fallback
- Retorna `List[Article]`

### `rss_reader.py`

- Lê lista de feeds de `config.yaml`
- Usa `feedparser` para parsear cada feed
- Filtra entradas publicadas nas últimas 24h
- Retorna `List[Article]`

### `analyzer.py`

- Agrupa artigos em batches de 10
- **System prompt** (cacheado via Anthropic prompt caching): contém critérios de relevância
- **User message**: array JSON com `title`, `source`, `content` dos N artigos do batch
- Modelo: `claude-haiku-4-5-20251001`
- Resposta esperada: array JSON com um resultado por artigo

**Critérios de relevância no system prompt:**

Priorizar (score alto):
- Redução de custos em tecnologia/ferramentas
- Novas tecnologias com aplicação prática imediata
- Oportunidades de negócio concretas
- Automação e produtividade
- IA aplicada (não benchmarks teóricos)
- Data Science com impacto real
- Open source relevante
- Mudanças regulatórias com impacto direto

Despriorizar (score baixo):
- Benchmarks sem impacto prático
- Marketing e anúncios corporativos
- Melhorias incrementais irrelevantes
- Discussões sem consequência prática

**Formato de resposta do Claude:**
```json
[
  {
    "title": "...",
    "relevance": 8,
    "summary": "resumo em poucas palavras",
    "why_it_matters": "por que isso importa",
    "impacts": ["impacto 1", "impacto 2"],
    "actions": ["ação possível 1"]
  }
]
```

### `telegram_sender.py`

- Classifica resultados: score ≥ 8 (🔴), score 6-7 (🟡), score ≤ 5 (⚪ ignorados)
- Monta mensagem única em Markdown
- Se ultrapassar 4096 caracteres, quebra em múltiplas mensagens mantendo cada artigo intacto
- Envia via Telegram Bot API

---

## Formato do Relatório

```
📊 *Inteligência Diária — DD/MM/AAAA*

Analisados: 28 conteúdos | Importantes: 4 | Ignorados: 24

━━━━━━━━━━━━━━━━━━━━━━
🔴 *[9/10] Título do artigo*
📌 Fonte: Morning Brew

Resumo executivo em uma ou duas frases.

Por que importa: motivo aqui.

Impactos:
• item 1
• item 2

Ações possíveis:
• ação 1

━━━━━━━━━━━━━━━━━━━━━━
🟡 *[7/10] Outro artigo*
📌 Fonte: TLDR
...

━━━━━━━━━━━━━━━━━━━━━━
⚪ *Ignorados (24)*

• Google anuncia atualização no Search Console — Google Blog
• Meta lança ferramenta interna de produtividade — The Verge
• Benchmark GPT-4o vs Gemini em tarefas de código — ML News
```

---

## GitHub Actions

**Workflow `daily.yml`:**
- Trigger: `schedule` às `0 10 * * *` (10h UTC = 7h BRT)
- Trigger manual: `workflow_dispatch` para testes
- Steps: checkout → setup Python → install deps → reconstruir arquivos de auth a partir de secrets → rodar `main.py`

**Secrets necessários:**
| Secret | Descrição |
|--------|-----------|
| `ANTHROPIC_API_KEY` | Chave da API Anthropic |
| `TELEGRAM_BOT_TOKEN` | Token do bot Telegram |
| `TELEGRAM_CHAT_ID` | ID do chat para receber o relatório |
| `GMAIL_TOKEN_JSON` | Conteúdo do `token.json` (gerado no setup inicial) |
| `GMAIL_CREDENTIALS_JSON` | Conteúdo do `credentials.json` do Google Cloud |

---

## Setup Inicial (uma vez)

1. Criar projeto no Google Cloud Console e habilitar Gmail API
2. Baixar `credentials.json`
3. Rodar `python setup_gmail_auth.py` localmente (abre browser para autorizar)
4. Serializar `token.json` e `credentials.json` como GitHub Secrets
5. Criar label `newsletters` no Gmail e configurar filtros para as newsletters desejadas
6. Criar bot no Telegram via BotFather e obter `TELEGRAM_BOT_TOKEN`
7. Obter `TELEGRAM_CHAT_ID` (conversar com o bot uma vez e consultar `/getUpdates`)

---

## Dependências

```
anthropic
google-auth
google-auth-oauthlib
google-api-python-client
feedparser
python-dotenv
requests
beautifulsoup4
pyyaml
```

---

## O que está fora do escopo (MVP)

- Frontend ou dashboard
- Banco de dados ou histórico persistente
- Multiusuário
- Memória de projetos pessoais
- Integração com carteira de investimentos
- Aprendizado de preferências
- Agrupamento de notícias semelhantes
