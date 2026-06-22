# Backend de LLM Plugável (LiteLLM) + README — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir trocar o provedor de LLM (Anthropic na nuvem por default, ou modelo local via Ollama/OpenAI-compatível) só por configuração, via LiteLLM, e adicionar um README open source ("Bem-te-vi") com os tiers de hardware.

**Architecture:** Um módulo `src/llm.py` expõe `complete(system, user, max_tokens) -> str` sobre `litellm.completion`. O `analyzer.py` e o `deduplicator.py` deixam de instanciar o SDK Anthropic direto e passam a chamar `complete(...)`. O provedor vive na string `LLM_MODEL`. Continua stateless.

**Tech Stack:** Python 3.11+, LiteLLM, pytest + pytest-mock.

**Spec:** `docs/superpowers/specs/2026-06-22-pluggable-llm-backend-design.md`

## Global Constraints

- Python 3.11+
- Default `LLM_MODEL` = `claude-haiku-4-5-20251001` (preserva o GitHub Actions atual)
- `LLM_MODEL` carrega o provedor embutido (ex: `ollama/qwen2.5:7b`); NÃO existe `LLM_BACKEND`
- `LLM_API_BASE` e `LLM_API_KEY` só são passados ao LiteLLM quando setados nas envs
- Sem prompt caching (`cache_control`) no caminho unificado
- `litellm` DEVE ser pinado com `==` (versão exata), nunca `>=`
- max_tokens preservados: analyzer = 4096, deduplicator = 2048
- Nome do programa no README: **Bem-te-vi**
- **Stateless:** nenhuma persistência entre execuções
- Todos os testes com `pytest`; mockar toda chamada externa

---

### Task 1: Módulo `src/llm.py` (LiteLLM)

**Files:**
- Create: `src/llm.py`
- Create: `tests/test_llm.py`
- Modify: `requirements.txt` (adicionar `litellm` pinado)

**Interfaces:**
- Produces: `complete(system: str, user: str, max_tokens: int = 4096) -> str` e `DEFAULT_MODEL = "claude-haiku-4-5-20251001"`

- [ ] **Step 1: Instalar o LiteLLM e pinar a versão**

```bash
pip install litellm
pip show litellm | grep -i version
```

Anote a versão exata mostrada (ex: `Version: 1.55.3`) e adicione ao **final** de `requirements.txt`:

```
litellm==1.55.3  # pinned; review on upgrade (litellm releases frequently)
```

Use a versão real que o `pip show` reportou no lugar de `1.55.3`.

- [ ] **Step 2: Escrever os testes que falham**

Crie `tests/test_llm.py`:

```python
import os
from unittest.mock import patch, MagicMock

from src.llm import complete, DEFAULT_MODEL


def _mock_completion(content="resposta"):
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]
    return resp


def test_complete_uses_default_model_when_unset():
    with patch.dict(os.environ, {}, clear=True), \
         patch("litellm.completion", return_value=_mock_completion()) as mock_c:
        complete("sys", "usr")
    assert mock_c.call_args.kwargs["model"] == DEFAULT_MODEL


def test_complete_honors_llm_model_env():
    with patch.dict(os.environ, {"LLM_MODEL": "ollama/qwen2.5:7b"}, clear=True), \
         patch("litellm.completion", return_value=_mock_completion()) as mock_c:
        complete("sys", "usr")
    assert mock_c.call_args.kwargs["model"] == "ollama/qwen2.5:7b"


def test_complete_includes_api_base_and_key_when_set():
    env = {"LLM_API_BASE": "http://localhost:11434", "LLM_API_KEY": "k"}
    with patch.dict(os.environ, env, clear=True), \
         patch("litellm.completion", return_value=_mock_completion()) as mock_c:
        complete("sys", "usr")
    kwargs = mock_c.call_args.kwargs
    assert kwargs["api_base"] == "http://localhost:11434"
    assert kwargs["api_key"] == "k"


def test_complete_omits_api_base_and_key_when_unset():
    with patch.dict(os.environ, {}, clear=True), \
         patch("litellm.completion", return_value=_mock_completion()) as mock_c:
        complete("sys", "usr")
    kwargs = mock_c.call_args.kwargs
    assert "api_base" not in kwargs
    assert "api_key" not in kwargs


def test_complete_passes_messages_and_max_tokens():
    with patch.dict(os.environ, {}, clear=True), \
         patch("litellm.completion", return_value=_mock_completion()) as mock_c:
        complete("the system", "the user", max_tokens=2048)
    kwargs = mock_c.call_args.kwargs
    assert kwargs["max_tokens"] == 2048
    assert kwargs["messages"] == [
        {"role": "system", "content": "the system"},
        {"role": "user", "content": "the user"},
    ]


def test_complete_returns_message_content():
    with patch.dict(os.environ, {}, clear=True), \
         patch("litellm.completion", return_value=_mock_completion("olá")):
        assert complete("sys", "usr") == "olá"
```

- [ ] **Step 3: Rodar para confirmar que falham**

Run: `python -m pytest tests/test_llm.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'src.llm'`

- [ ] **Step 4: Implementar `src/llm.py`**

```python
import os

import litellm

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def complete(system: str, user: str, max_tokens: int = 4096) -> str:
    kwargs = {
        "model": os.getenv("LLM_MODEL", DEFAULT_MODEL),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    api_base = os.getenv("LLM_API_BASE")
    if api_base:
        kwargs["api_base"] = api_base
    api_key = os.getenv("LLM_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key
    response = litellm.completion(**kwargs)
    return response.choices[0].message.content
```

- [ ] **Step 5: Rodar para confirmar que passam**

Run: `python -m pytest tests/test_llm.py -v`
Expected: 6 PASSED

- [ ] **Step 6: Commit**

```bash
git add src/llm.py tests/test_llm.py requirements.txt
git commit -m "feat: add LiteLLM-backed complete() LLM abstraction"
```

---

### Task 2: Migrar `analyzer.py` para `complete()`

**Files:**
- Modify: `src/analyzer.py`
- Modify: `tests/test_analyzer.py`

**Interfaces:**
- Consumes: `complete` de `src.llm`
- Produces: `analyze(articles) -> list[AnalysisResult]` (assinatura e comportamento inalterados)

- [ ] **Step 1: Reescrever os testes para mockar `complete`**

Substitua todo o conteúdo de `tests/test_analyzer.py` por:

```python
import json
from unittest.mock import patch
from datetime import datetime, timezone
from src.analyzer import analyze, _build_batches
from src.models import Article, AnalysisResult


def _make_article(title: str, source: str = "Test") -> Article:
    return Article(
        source=source,
        title=title,
        content="Some content about " + title,
        url="https://example.com",
        published_at=datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc),
    )


def test_build_batches_splits_correctly():
    articles = [_make_article(f"Article {i}") for i in range(25)]
    batches = _build_batches(articles, batch_size=10)
    assert len(batches) == 3
    assert len(batches[0]) == 10
    assert len(batches[1]) == 10
    assert len(batches[2]) == 5


def test_build_batches_empty():
    assert _build_batches([], batch_size=10) == []


def test_analyze_returns_analysis_results():
    articles = [_make_article("OpenAI cuts API prices by 80%", "TechCrunch")]
    payload = json.dumps([
        {
            "title": "OpenAI cuts API prices by 80%",
            "relevance": 9,
            "summary": "Major price cut for GPT APIs",
            "why_it_matters": "Reduces AI project costs significantly",
            "impacts": ["Cheaper AI projects", "More competition"],
            "actions": ["Review current API costs"],
        }
    ])
    with patch("src.analyzer.complete", return_value=payload):
        results = analyze(articles)

    assert len(results) == 1
    assert isinstance(results[0], AnalysisResult)
    assert results[0].relevance == 9
    assert results[0].title == "OpenAI cuts API prices by 80%"
    assert results[0].source == "TechCrunch"
    assert len(results[0].impacts) == 2


def test_analyze_empty_list():
    results = analyze([])
    assert results == []


def test_analyze_handles_api_error():
    articles = [_make_article("Some article")]
    with patch("src.analyzer.complete", side_effect=Exception("API error")):
        results = analyze(articles)
    assert results == []


def test_analyze_handles_fewer_results_than_articles():
    articles = [_make_article(f"Article {i}") for i in range(3)]
    payload = json.dumps([
        {"title": "Article 0", "relevance": 7, "summary": "summary",
         "why_it_matters": "matters", "impacts": [], "actions": []}
    ])
    with patch("src.analyzer.complete", return_value=payload):
        results = analyze(articles)
    assert len(results) == 1
    assert results[0].source == "Test"


def test_analyze_handles_more_results_than_articles():
    articles = [_make_article("Only article", source="RealSource")]
    payload = json.dumps([
        {"title": "Only article", "relevance": 7, "summary": "summary",
         "why_it_matters": "matters", "impacts": [], "actions": []},
        {"title": "Extra article", "relevance": 5, "summary": "extra",
         "why_it_matters": "extra", "impacts": [], "actions": []},
    ])
    with patch("src.analyzer.complete", return_value=payload):
        results = analyze(articles)
    assert len(results) == 1
    assert results[0].source == "RealSource"
    assert results[0].title == "Only article"


def test_analyze_propagates_sources_from_article():
    article = _make_article("Multi-source news", "TechCrunch")
    article.sources = ["TechCrunch", "HN"]
    payload = json.dumps([
        {"title": "Multi-source news", "relevance": 9, "summary": "s",
         "why_it_matters": "w", "impacts": [], "actions": []}
    ])
    with patch("src.analyzer.complete", return_value=payload):
        results = analyze([article])
    assert results[0].sources == ["TechCrunch", "HN"]


def test_analyze_defaults_sources_to_single_source():
    article = _make_article("Single", "Nord")
    payload = json.dumps([
        {"title": "Single", "relevance": 7, "summary": "s",
         "why_it_matters": "w", "impacts": [], "actions": []}
    ])
    with patch("src.analyzer.complete", return_value=payload):
        results = analyze([article])
    assert results[0].sources == ["Nord"]
```

- [ ] **Step 2: Rodar para confirmar que falham**

Run: `python -m pytest tests/test_analyzer.py -v`
Expected: FAIL (os testes referenciam `src.analyzer.complete`, que ainda não existe; `analyze` ainda usa o cliente Anthropic)

- [ ] **Step 3: Migrar `src/analyzer.py`**

No topo do arquivo, troque os imports. Substitua:

```python
import json
import logging
import os

import anthropic

from src.models import Article, AnalysisResult
```

por:

```python
import json
import logging

from src.llm import complete
from src.models import Article, AnalysisResult
```

Depois, substitua a função `analyze` inteira por:

```python
def analyze(articles: list[Article]) -> list[AnalysisResult]:
    if not articles:
        return []

    batches = _build_batches(articles, batch_size=10)
    all_results: list[AnalysisResult] = []

    for batch in batches:
        payload = [
            {"title": a.title, "source": a.source, "content": a.content[:2000]}
            for a in batch
        ]
        try:
            text = complete(
                SYSTEM_PROMPT,
                json.dumps(payload, ensure_ascii=False),
                max_tokens=4096,
            )
            results = _parse_response(text, batch)
            all_results.extend(results)
        except Exception as e:
            logger.error("Analyzer batch failed: %s", e)

    return all_results
```

`SYSTEM_PROMPT`, `_build_batches` e `_parse_response` permanecem como estão.

- [ ] **Step 4: Rodar para confirmar que passam**

Run: `python -m pytest tests/test_analyzer.py -v`
Expected: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add src/analyzer.py tests/test_analyzer.py
git commit -m "refactor: analyzer uses complete() instead of Anthropic SDK"
```

---

### Task 3: Migrar `deduplicator.py` para `complete()`

**Files:**
- Modify: `src/deduplicator.py`
- Modify: `tests/test_deduplicator.py`

**Interfaces:**
- Consumes: `complete` de `src.llm`
- Produces: `deduplicate(articles, status=None) -> list[Article]` (inalterado)

- [ ] **Step 1: Reescrever os testes para mockar `complete`**

Substitua todo o conteúdo de `tests/test_deduplicator.py` por:

```python
import json
from datetime import datetime, timezone
from unittest.mock import patch

from src.deduplicator import deduplicate
from src.models import Article
from src.run_status import RunStatus


def _make_article(title: str, source: str, content: str) -> Article:
    return Article(
        source=source, title=title, content=content,
        url="https://example.com",
        published_at=datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc),
    )


def test_deduplicate_groups_same_story():
    articles = [
        _make_article("OpenAI cuts prices", "TechCrunch", "long content here xxxx"),
        _make_article("Random unrelated", "HN", "other"),
        _make_article("OpenAI price cut", "Nord", "short"),
    ]
    with patch("src.deduplicator.complete", return_value=json.dumps([[0, 2], [1]])):
        result = deduplicate(articles)

    assert len(result) == 2
    rep = next(r for r in result if r.title == "OpenAI cuts prices")
    assert rep.sources == ["Nord", "TechCrunch"]


def test_representative_is_longest_content():
    articles = [
        _make_article("A", "S1", "short"),
        _make_article("B", "S2", "a much longer body of content"),
    ]
    with patch("src.deduplicator.complete", return_value=json.dumps([[0, 1]])):
        result = deduplicate(articles)

    assert len(result) == 1
    assert result[0].title == "B"
    assert result[0].sources == ["S1", "S2"]


def test_deduplicate_empty_returns_empty():
    assert deduplicate([]) == []


def test_deduplicate_fallback_on_error_sets_sources_and_warns():
    articles = [
        _make_article("A", "S1", "x"),
        _make_article("B", "S2", "y"),
    ]
    status = RunStatus()
    with patch("src.deduplicator.complete", side_effect=Exception("API down")):
        result = deduplicate(articles, status=status)

    assert len(result) == 2
    assert result[0].sources == ["S1"]
    assert result[1].sources == ["S2"]
    assert len(status.warnings) == 1


def test_deduplicate_fills_missing_indices_as_singletons():
    articles = [
        _make_article("A", "S1", "x"),
        _make_article("B", "S2", "y"),
        _make_article("C", "S3", "z"),
    ]
    with patch("src.deduplicator.complete", return_value=json.dumps([[0, 1]])):
        result = deduplicate(articles)

    assert len(result) == 2
    titles = {r.title for r in result}
    assert "C" in titles
```

- [ ] **Step 2: Rodar para confirmar que falham**

Run: `python -m pytest tests/test_deduplicator.py -v`
Expected: FAIL (testes referenciam `src.deduplicator.complete`, ainda inexistente)

- [ ] **Step 3: Migrar `src/deduplicator.py`**

No topo, substitua:

```python
import json
import logging
import os

import anthropic

from src.models import Article
from src.run_status import RunStatus
```

por:

```python
import json
import logging

from src.llm import complete
from src.models import Article
from src.run_status import RunStatus
```

Dentro de `deduplicate`, substitua o bloco `try:` que cria o cliente e chama a API. Troque:

```python
    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": DEDUP_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
            ],
        )
        groups = _parse_groups(response.content[0].text, len(articles))
    except Exception as e:
```

por:

```python
    try:
        text = complete(
            DEDUP_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            max_tokens=2048,
        )
        groups = _parse_groups(text, len(articles))
    except Exception as e:
```

`DEDUP_PROMPT`, `_no_dedup`, `_parse_groups` e o restante de `deduplicate` (montagem do `payload`, fallback, representantes) permanecem.

- [ ] **Step 4: Rodar para confirmar que passam**

Run: `python -m pytest tests/test_deduplicator.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/deduplicator.py tests/test_deduplicator.py
git commit -m "refactor: deduplicator uses complete() instead of Anthropic SDK"
```

---

### Task 4: Limpeza de dependência + `.env.example`

**Files:**
- Modify: `requirements.txt` (remover `anthropic`)
- Modify: `.env.example`

**Interfaces:**
- Consumes: nada (cleanup); depende das Tasks 2 e 3 já terem removido `import anthropic`

- [ ] **Step 1: Confirmar que nada importa `anthropic` diretamente**

Run: `python -m pytest -q` e, em seguida, verifique que não há mais import direto:

```bash
grep -rn "import anthropic" src/ tests/ main.py
```

Expected: a suíte passa inteira; o `grep` não retorna nenhuma linha.

- [ ] **Step 2: Remover `anthropic` do `requirements.txt`**

Apague a linha:

```
anthropic>=0.40.0
```

(As demais linhas, incluindo `litellm==...` da Task 1, permanecem.)

- [ ] **Step 3: Atualizar `.env.example`**

Substitua todo o conteúdo de `.env.example` por:

```
ANTHROPIC_API_KEY=your_anthropic_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
GMAIL_LABEL=newsletters

# LLM (default: Anthropic na nuvem). Para rodar local, veja o README.
# LLM_MODEL=claude-haiku-4-5-20251001
# LLM_API_BASE=http://localhost:11434
# LLM_API_KEY=
```

- [ ] **Step 4: Rodar a suíte completa**

Run: `python -m pytest -q`
Expected: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example
git commit -m "chore: drop anthropic dep, document LLM env vars in .env.example"
```

---

### Task 5: README open source ("Bem-te-vi")

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: as envs `LLM_MODEL`, `LLM_API_BASE`, `LLM_API_KEY` definidas na Task 1

- [ ] **Step 1: Criar `README.md`**

Crie `README.md` na raiz com este conteúdo:

````markdown
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
````

- [ ] **Step 2: Verificar a renderização**

Run: `python -m pytest -q`
Expected: todos PASSED (sanidade — o README não quebra nada). Confira visualmente que a tabela de hardware e os blocos de código estão bem formados.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add open-source README (Bem-te-vi) with hardware tiers"
```

---

## Self-Review

**Cobertura do spec:**

| Requisito do spec | Task |
|---|---|
| `src/llm.py` com `complete()` via LiteLLM | Task 1 |
| Config `LLM_MODEL`/`LLM_API_BASE`/`LLM_API_KEY` (sem `LLM_BACKEND`) | Tasks 1, 4 |
| `api_base`/`api_key` só quando setados | Task 1 |
| Default `claude-haiku-4-5-20251001` | Task 1 |
| Sem prompt caching no caminho unificado | Tasks 2, 3 |
| Migrar analyzer | Task 2 |
| Migrar deduplicator | Task 3 |
| `litellm` pinado com `==` | Task 1 |
| Remover `anthropic` do requirements | Task 4 |
| `.env.example` com `LLM_*` | Task 4 |
| README "Bem-te-vi" + tiers de hardware | Task 5 |
| GitHub Actions sem mudança | (verificado — nenhuma task altera o workflow) |

**Consistência de tipos:** `complete(system, user, max_tokens=4096) -> str` definida na Task 1, consumida nas Tasks 2 (`max_tokens=4096`) e 3 (`max_tokens=2048`). Mock em `src.analyzer.complete` / `src.deduplicator.complete` bate com o import `from src.llm import complete` em cada módulo.

**Placeholder scan:** o único `<...>` é a versão do LiteLLM na Task 1, que é instrução explícita de capturar a versão resolvida pelo `pip` — não um TBD.
