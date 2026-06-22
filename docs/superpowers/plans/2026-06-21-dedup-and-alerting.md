# Dedup Semântica + Alertas de Saúde — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agrupar notícias do mesmo fato num único item do relatório (dedup semântica via Haiku) e avisar o usuário quando o pipeline degrada (alertas de saúde), tudo sem persistência entre execuções.

**Architecture:** Dois passos novos no pipeline linear existente — um passo de dedup entre coleta e análise, e um acumulador de avisos (`RunStatus`) que percorre o run e vira rodapé do relatório (ou mensagem dedicada + exit code em caso de crash). Nenhum estado é gravado entre execuções; tudo vive em memória durante um único run.

**Tech Stack:** Python 3.11+, anthropic SDK (Claude Haiku), requests, pytest + pytest-mock.

**Spec:** `docs/superpowers/specs/2026-06-21-dedup-and-alerting-design.md`

## Global Constraints

- Python 3.11+
- Model: `claude-haiku-4-5-20251001` (dedup e análise)
- Batch size da análise: 10 artigos por chamada (inalterado)
- Relevância: ≥8 → 🔴, 6-7 → 🟡, ≤5 → ⚪
- Telegram: `parse_mode=HTML`, limite 4096 chars, escapar com `html.escape`
- Saída de texto da análise em pt-BR (já implementado)
- **Stateless:** nenhuma persistência entre execuções (requisito do GitHub Actions)
- Todos os testes com `pytest`; mockar toda chamada externa (Anthropic, requests, Gmail)

---

### Task 1: Campo `sources` nos modelos

**Files:**
- Modify: `src/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `Article.sources: list[str]` (default `[]`), `AnalysisResult.sources: list[str]` (default `[]`)

- [ ] **Step 1: Escrever os testes que falham**

Adicione ao final de `tests/test_models.py`:

```python
def test_article_has_sources_default_empty():
    from src.models import Article
    from datetime import datetime, timezone
    article = Article(
        source="Test",
        title="T",
        content="c",
        url="https://example.com",
        published_at=datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc),
    )
    assert article.sources == []


def test_analysis_result_has_sources_default_empty():
    from src.models import AnalysisResult
    result = AnalysisResult(
        title="T", source="S", url="u", relevance=8,
        summary="s", why_it_matters="w",
    )
    assert result.sources == []
```

- [ ] **Step 2: Rodar para confirmar que falham**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL com `AttributeError: 'Article' object has no attribute 'sources'`

- [ ] **Step 3: Implementar**

Em `src/models.py`, adicione o campo a cada dataclass (sempre por último, pois têm default):

```python
@dataclass
class Article:
    source: str
    title: str
    content: str
    url: str
    published_at: datetime
    sources: list[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    title: str
    source: str
    url: str
    relevance: int
    summary: str
    why_it_matters: str
    impacts: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Rodar para confirmar que passam**

Run: `python -m pytest tests/test_models.py -v`
Expected: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add sources field to Article and AnalysisResult"
```

---

### Task 2: `RunStatus` (acumulador de avisos)

**Files:**
- Create: `src/run_status.py`
- Test: `tests/test_run_status.py`

**Interfaces:**
- Produces: `RunStatus` dataclass com `warnings: list[str]` e método `add(message: str) -> None`

- [ ] **Step 1: Escrever os testes que falham**

Crie `tests/test_run_status.py`:

```python
from src.run_status import RunStatus


def test_runstatus_starts_empty():
    status = RunStatus()
    assert status.warnings == []


def test_runstatus_add_appends():
    status = RunStatus()
    status.add("Gmail: label não encontrada")
    status.add("RSS fora do ar")
    assert status.warnings == ["Gmail: label não encontrada", "RSS fora do ar"]
```

- [ ] **Step 2: Rodar para confirmar que falham**

Run: `python -m pytest tests/test_run_status.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'src.run_status'`

- [ ] **Step 3: Implementar**

Crie `src/run_status.py`:

```python
from dataclasses import dataclass, field


@dataclass
class RunStatus:
    warnings: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.warnings.append(message)
```

- [ ] **Step 4: Rodar para confirmar que passam**

Run: `python -m pytest tests/test_run_status.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/run_status.py tests/test_run_status.py
git commit -m "feat: add RunStatus accumulator for run-health warnings"
```

---

### Task 3: Deduplicador semântico

**Files:**
- Create: `src/deduplicator.py`
- Test: `tests/test_deduplicator.py`

**Interfaces:**
- Consumes: `Article` de `src.models`; `RunStatus` de `src.run_status` (opcional); env `ANTHROPIC_API_KEY`
- Produces: `deduplicate(articles: list[Article], status: RunStatus | None = None) -> list[Article]` — retorna um representante por grupo, com `representante.sources` preenchido. Em falha, retorna cada artigo como grupo único (sem perda) e registra aviso.

- [ ] **Step 1: Escrever os testes que falham**

Crie `tests/test_deduplicator.py`:

```python
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src.deduplicator import deduplicate
from src.models import Article
from src.run_status import RunStatus


def _make_article(title: str, source: str, content: str) -> Article:
    return Article(
        source=source, title=title, content=content,
        url="https://example.com",
        published_at=datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc),
    )


def _mock_groups_response(groups):
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps(groups))]
    return response


def test_deduplicate_groups_same_story():
    articles = [
        _make_article("OpenAI cuts prices", "TechCrunch", "long content here xxxx"),
        _make_article("Random unrelated", "HN", "other"),
        _make_article("OpenAI price cut", "Nord", "short"),
    ]
    with patch("anthropic.Anthropic") as cls:
        client = MagicMock()
        cls.return_value = client
        client.messages.create.return_value = _mock_groups_response([[0, 2], [1]])
        result = deduplicate(articles)

    assert len(result) == 2
    # grupo [0,2]: representante é o de maior content (índice 0)
    rep = next(r for r in result if r.title == "OpenAI cuts prices")
    assert rep.sources == ["Nord", "TechCrunch"]  # ordenado, sem repetição


def test_representative_is_longest_content():
    articles = [
        _make_article("A", "S1", "short"),
        _make_article("B", "S2", "a much longer body of content"),
    ]
    with patch("anthropic.Anthropic") as cls:
        client = MagicMock()
        cls.return_value = client
        client.messages.create.return_value = _mock_groups_response([[0, 1]])
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
    with patch("anthropic.Anthropic") as cls:
        client = MagicMock()
        cls.return_value = client
        client.messages.create.side_effect = Exception("API down")
        result = deduplicate(articles, status=status)

    assert len(result) == 2  # nada perdido
    assert result[0].sources == ["S1"]
    assert result[1].sources == ["S2"]
    assert len(status.warnings) == 1


def test_deduplicate_fills_missing_indices_as_singletons():
    articles = [
        _make_article("A", "S1", "x"),
        _make_article("B", "S2", "y"),
        _make_article("C", "S3", "z"),
    ]
    with patch("anthropic.Anthropic") as cls:
        client = MagicMock()
        cls.return_value = client
        # modelo esqueceu o índice 2
        client.messages.create.return_value = _mock_groups_response([[0, 1]])
        result = deduplicate(articles)

    assert len(result) == 2  # grupo [0,1] + singleton [2]
    titles = {r.title for r in result}
    assert "C" in titles
```

- [ ] **Step 2: Rodar para confirmar que falham**

Run: `python -m pytest tests/test_deduplicator.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'src.deduplicator'`

- [ ] **Step 3: Implementar**

Crie `src/deduplicator.py`:

```python
import json
import logging
import os

import anthropic

from src.models import Article
from src.run_status import RunStatus

logger = logging.getLogger(__name__)

DEDUP_PROMPT = """You are a news deduplication assistant. You receive a JSON array of articles, each with an "index", "title", and "source". Group together the articles that report the SAME underlying news event or story, even if their titles differ or they come from different sources. Articles about different events must be in different groups.

Return ONLY a JSON array of groups, where each group is an array of the integer indices belonging to it. Every input index must appear in exactly one group. Example: [[0, 3], [1], [2, 4]]. No markdown, no explanation."""


def _no_dedup(articles: list[Article]) -> list[Article]:
    for a in articles:
        a.sources = [a.source]
    return articles


def _parse_groups(text: str, n: int) -> list[list[int]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            raise
        data = json.loads(text[start:end])

    seen: set[int] = set()
    groups: list[list[int]] = []
    for group in data:
        valid = [i for i in group if isinstance(i, int) and 0 <= i < n and i not in seen]
        seen.update(valid)
        if valid:
            groups.append(valid)
    for i in range(n):  # índices que o modelo deixou de fora viram singletons
        if i not in seen:
            groups.append([i])
    return groups


def deduplicate(articles: list[Article], status: RunStatus | None = None) -> list[Article]:
    if not articles:
        return []
    if len(articles) == 1:
        return _no_dedup(articles)

    payload = [
        {"index": i, "title": a.title, "source": a.source}
        for i, a in enumerate(articles)
    ]
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
        logger.error("Deduplication failed, falling back to no-dedup: %s", e)
        if status is not None:
            status.add("Deduplicação falhou; relatório pode conter notícias repetidas")
        return _no_dedup(articles)

    representatives: list[Article] = []
    for group in groups:
        members = [articles[i] for i in group]
        rep = max(members, key=lambda a: len(a.content))
        rep.sources = sorted({m.source for m in members})
        representatives.append(rep)
    return representatives
```

- [ ] **Step 4: Rodar para confirmar que passam**

Run: `python -m pytest tests/test_deduplicator.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/deduplicator.py tests/test_deduplicator.py
git commit -m "feat: semantic deduplicator with graceful fallback"
```

---

### Task 4: Analyzer propaga `sources`

**Files:**
- Modify: `src/analyzer.py` (função `_parse_response`, ~linha 72)
- Test: `tests/test_analyzer.py`

**Interfaces:**
- Consumes: `Article.sources`
- Produces: cada `AnalysisResult` sai com `sources = article.sources or [article.source]`

- [ ] **Step 1: Escrever os testes que falham**

Adicione ao final de `tests/test_analyzer.py`:

```python
def test_analyze_propagates_sources_from_article():
    import json as _json
    article = _make_article("Multi-source news", "TechCrunch")
    article.sources = ["TechCrunch", "HN"]

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps([
        {"title": "Multi-source news", "relevance": 9, "summary": "s",
         "why_it_matters": "w", "impacts": [], "actions": []}
    ]))]

    with patch("anthropic.Anthropic") as cls:
        client = MagicMock()
        cls.return_value = client
        client.messages.create.return_value = mock_response
        results = analyze([article])

    assert results[0].sources == ["TechCrunch", "HN"]


def test_analyze_defaults_sources_to_single_source():
    import json as _json
    article = _make_article("Single", "Nord")  # sources fica []

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps([
        {"title": "Single", "relevance": 7, "summary": "s",
         "why_it_matters": "w", "impacts": [], "actions": []}
    ]))]

    with patch("anthropic.Anthropic") as cls:
        client = MagicMock()
        cls.return_value = client
        client.messages.create.return_value = mock_response
        results = analyze([article])

    assert results[0].sources == ["Nord"]
```

- [ ] **Step 2: Rodar para confirmar que falham**

Run: `python -m pytest tests/test_analyzer.py -k sources -v`
Expected: FAIL — `sources` vem `[]` em vez do esperado

- [ ] **Step 3: Implementar**

Em `src/analyzer.py`, na construção do `AnalysisResult` dentro de `_parse_response`, adicione o campo `sources`:

```python
        results.append(
            AnalysisResult(
                title=item.get("title", article.title),
                source=article.source,
                url=article.url,
                relevance=int(item.get("relevance", 0)),
                summary=item.get("summary", ""),
                why_it_matters=item.get("why_it_matters", ""),
                impacts=item.get("impacts", []),
                actions=item.get("actions", []),
                sources=article.sources or [article.source],
            )
        )
```

- [ ] **Step 4: Rodar para confirmar que passam**

Run: `python -m pytest tests/test_analyzer.py -v`
Expected: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add src/analyzer.py tests/test_analyzer.py
git commit -m "feat: analyzer propagates sources into AnalysisResult"
```

---

### Task 5: Relatório mostra "Visto em" para múltiplas fontes

**Files:**
- Modify: `src/telegram_sender.py` (função `format_report`, linha da fonte ~32)
- Test: `tests/test_telegram_sender.py`

**Interfaces:**
- Consumes: `AnalysisResult.sources`
- Produces: linha `📌 Visto em: A, B, C` quando `len(sources) > 1`, senão `📌 Fonte: X`

- [ ] **Step 1: Escrever os testes que falham**

Adicione ao final de `tests/test_telegram_sender.py`:

```python
def test_format_report_multi_source_shows_visto_em():
    result = _make_result("Big news", 9)
    result.sources = ["TechCrunch", "HN", "Nord"]
    report = format_report([result], total_analyzed=1)
    assert "Visto em: TechCrunch, HN, Nord" in report
    assert "📌 Fonte:" not in report


def test_format_report_single_source_shows_fonte():
    result = _make_result("News", 9)
    result.sources = ["TechCrunch"]
    report = format_report([result], total_analyzed=1)
    assert "📌 Fonte: Test" in report  # usa result.source
    assert "Visto em:" not in report
```

> Nota: `_make_result` cria `source="Test"`; com `sources` de 1 item a linha usa `result.source`.

- [ ] **Step 2: Rodar para confirmar que falham**

Run: `python -m pytest tests/test_telegram_sender.py -k "visto or fonte" -v`
Expected: FAIL — "Visto em" ainda não existe

- [ ] **Step 3: Implementar**

Em `src/telegram_sender.py`, dentro do loop de `important`, substitua a linha da fonte. Troque:

```python
            f"📌 Fonte: {html.escape(result.source)}",
```

por:

```python
            (
                f"📌 Visto em: {', '.join(html.escape(s) for s in result.sources)}"
                if len(result.sources) > 1
                else f"📌 Fonte: {html.escape(result.source)}"
            ),
```

- [ ] **Step 4: Rodar para confirmar que passam**

Run: `python -m pytest tests/test_telegram_sender.py -v`
Expected: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add src/telegram_sender.py tests/test_telegram_sender.py
git commit -m "feat: report shows 'Visto em' for multi-source news"
```

---

### Task 6: Rodapé de avisos, `send_report` retorna bool, `send_alert`

**Files:**
- Modify: `src/telegram_sender.py` (`format_report`, `send_report`; adicionar `_post_message` e `send_alert`)
- Test: `tests/test_telegram_sender.py`

**Interfaces:**
- Produces:
  - `format_report(results, total_analyzed, warnings: list[str] | None = None) -> str`
  - `send_report(results, total_analyzed, warnings: list[str] | None = None) -> bool`
  - `send_alert(text: str) -> bool`
  - `_post_message(token, chat_id, text) -> bool` (privado)

- [ ] **Step 1: Escrever os testes que falham**

Adicione ao final de `tests/test_telegram_sender.py`:

```python
def test_format_report_with_warnings_shows_footer():
    result = _make_result("News", 8)
    report = format_report([result], total_analyzed=1, warnings=["Gmail: label não encontrada"])
    assert "Avisos" in report
    assert "Gmail: label não encontrada" in report


def test_format_report_without_warnings_no_footer():
    result = _make_result("News", 8)
    report = format_report([result], total_analyzed=1)
    assert "Avisos" not in report


def test_send_report_returns_true_on_success():
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1"}), \
         patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        ok = send_report([_make_result("N", 8)], total_analyzed=1)
    assert ok is True


def test_send_report_returns_false_on_api_failure():
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1"}), \
         patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=False, text="403 Forbidden")
        ok = send_report([_make_result("N", 8)], total_analyzed=1)
    assert ok is False


def test_send_report_returns_false_without_credentials():
    with patch.dict("os.environ", {}, clear=True):
        ok = send_report([_make_result("N", 8)], total_analyzed=1)
    assert ok is False


def test_send_alert_posts_and_returns_true():
    from src.telegram_sender import send_alert
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1"}), \
         patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        ok = send_alert("🚨 Pipeline falhou: boom")
    assert ok is True
    assert "sendMessage" in mock_post.call_args[0][0]
```

Atualize o import no topo do arquivo de teste para incluir `send_alert`:

```python
from src.telegram_sender import format_report, split_messages, send_report, send_alert
```

- [ ] **Step 2: Rodar para confirmar que falham**

Run: `python -m pytest tests/test_telegram_sender.py -k "warnings or returns or alert" -v`
Expected: FAIL (assinaturas/funções novas ainda não existem)

- [ ] **Step 3: Implementar**

Em `src/telegram_sender.py`:

(a) Estenda `format_report` para aceitar `warnings` e anexar o rodapé. Mude a assinatura e adicione o bloco antes do `return`:

```python
def format_report(results: list[AnalysisResult], total_analyzed: int, warnings: list[str] | None = None) -> str:
```

E logo antes de `return "\n".join(lines)`:

```python
    if warnings:
        lines.append(f"\n{SEPARATOR}")
        lines.append("⚠️ <b>Avisos</b>\n")
        for w in warnings:
            lines.append(f"• {html.escape(w)}")
```

(b) Adicione o helper privado e a função de alerta, e reescreva `send_report` para usar o helper e retornar bool:

```python
def _post_message(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if not response.ok:
            logger.error("Telegram API error: %s", response.text)
            return False
        return True
    except Exception as e:
        logger.error("Failed to send Telegram message: %s", e)
        return False


def send_report(results: list[AnalysisResult], total_analyzed: int, warnings: list[str] | None = None) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False

    report = format_report(results, total_analyzed, warnings)
    messages = split_messages(report)

    all_ok = True
    for message in messages:
        if not _post_message(token, chat_id, message):
            all_ok = False
    return all_ok


def send_alert(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set; cannot send alert")
        return False
    return _post_message(token, chat_id, text)
```

- [ ] **Step 4: Rodar para confirmar que passam**

Run: `python -m pytest tests/test_telegram_sender.py -v`
Expected: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add src/telegram_sender.py tests/test_telegram_sender.py
git commit -m "feat: warnings footer, send_report bool, send_alert"
```

---

### Task 7: Readers registram avisos no `RunStatus`

**Files:**
- Modify: `src/gmail_reader.py` (`read_gmail`)
- Modify: `src/rss_reader.py` (`read_rss_feeds`)
- Test: `tests/test_gmail_reader.py`, `tests/test_rss_reader.py`

**Interfaces:**
- Produces:
  - `read_gmail(label: str = "newsletters", status: RunStatus | None = None) -> list[Article]`
  - `read_rss_feeds(config_path: str = "config.yaml", status: RunStatus | None = None) -> list[Article]`
- Comportamento sem `status` (None) é idêntico ao atual.

- [ ] **Step 1: Corrigir o teste de tempo já existente do Gmail**

O teste `test_read_gmail_returns_articles` usa data fixa (`20 Jun 2026 08:00`) que cai fora da janela de 24h conforme os dias passam. Torne-o relativo ao agora. Em `tests/test_gmail_reader.py`, dentro de `test_read_gmail_returns_articles`, substitua o header `Date` fixo por um dinâmico. Adicione no topo do arquivo:

```python
from datetime import datetime, timezone
from email.utils import format_datetime
```

E troque a linha do header Date:

```python
                {"name": "Date", "value": "Fri, 20 Jun 2026 08:00:00 +0000"},
```

por:

```python
                {"name": "Date", "value": format_datetime(datetime.now(timezone.utc))},
```

- [ ] **Step 2: Escrever os testes de aviso que falham**

Adicione a `tests/test_gmail_reader.py`:

```python
def test_read_gmail_warns_when_label_missing():
    from src.run_status import RunStatus
    mock_service = MagicMock()
    mock_service.users().labels().list().execute.return_value = {
        "labels": [{"id": "X", "name": "outra"}]
    }
    status = RunStatus()
    with patch("src.gmail_reader._build_service", return_value=mock_service):
        articles = read_gmail("newsletters", status=status)
    assert articles == []
    assert any("newsletters" in w for w in status.warnings)
```

Adicione a `tests/test_rss_reader.py`:

```python
def test_read_rss_warns_when_feed_down(tmp_path):
    from src.run_status import RunStatus
    config_file = tmp_path / "config.yaml"
    config_file.write_text("rss_feeds:\n  - name: TechCrunch\n    url: http://x/rss\n")
    status = RunStatus()
    with patch("feedparser.parse", side_effect=Exception("network error")):
        articles = read_rss_feeds(str(config_file), status=status)
    assert articles == []
    assert any("TechCrunch" in w for w in status.warnings)
```

- [ ] **Step 3: Rodar para confirmar que falham**

Run: `python -m pytest tests/test_gmail_reader.py tests/test_rss_reader.py -v`
Expected: os dois testes novos FAIL com `TypeError: ... unexpected keyword argument 'status'`

- [ ] **Step 4: Implementar no Gmail reader**

Em `src/gmail_reader.py`, importe o tipo e altere a assinatura e os pontos de falha:

Topo do arquivo (após os imports existentes):

```python
from src.run_status import RunStatus
```

Assinatura:

```python
def read_gmail(label: str = "newsletters", status: RunStatus | None = None) -> list[Article]:
```

No `except` do build do serviço:

```python
    except Exception as e:
        logger.error("Failed to build Gmail service: %s", e)
        if status is not None:
            status.add("Gmail: falha de autenticação")
        return []
```

No bloco de label não encontrada:

```python
        if not label_id:
            logger.warning("Gmail label '%s' not found", label)
            if status is not None:
                status.add(f"Gmail: label '{label}' não encontrada")
            return []
```

No `except` da listagem de mensagens:

```python
    except Exception as e:
        logger.error("Failed to list Gmail messages: %s", e)
        if status is not None:
            status.add("Gmail: falha ao listar mensagens")
        return []
```

- [ ] **Step 5: Implementar no RSS reader**

Em `src/rss_reader.py`, importe o tipo e altere a assinatura e o ponto de falha do feed:

Topo do arquivo:

```python
from src.run_status import RunStatus
```

Assinatura:

```python
def read_rss_feeds(config_path: str = "config.yaml", status: RunStatus | None = None) -> list[Article]:
```

No `except FileNotFoundError`:

```python
    except FileNotFoundError:
        logger.warning("config.yaml not found at %s", config_path)
        if status is not None:
            status.add("RSS: config.yaml não encontrado")
        return []
```

No `except` da `feedparser.parse`:

```python
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            logger.error("Failed to fetch feed %s: %s", url, e)
            if status is not None:
                status.add(f"RSS '{name}': feed fora do ar")
            continue
```

- [ ] **Step 6: Rodar para confirmar que passam**

Run: `python -m pytest tests/test_gmail_reader.py tests/test_rss_reader.py -v`
Expected: todos PASSED (inclusive o de tempo corrigido)

- [ ] **Step 7: Commit**

```bash
git add src/gmail_reader.py src/rss_reader.py tests/test_gmail_reader.py tests/test_rss_reader.py
git commit -m "feat: readers report partial failures via RunStatus; fix time-dependent gmail test"
```

---

### Task 8: Wiring no `main.py` (dedup + status + exit codes)

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `deduplicate`, `RunStatus`, `send_alert`, `read_gmail(status=)`, `read_rss_feeds(status=)`, `send_report(...) -> bool`
- Produces: pipeline com dedup, coleta de avisos, rodapé no relatório, `send_alert` + `sys.exit(1)` em crash, `sys.exit(1)` em falha de entrega

- [ ] **Step 1: Reescrever os testes**

Substitua todo o conteúdo de `tests/test_main.py` por:

```python
import pytest
from unittest.mock import patch
from datetime import datetime, timezone
from src.models import Article, AnalysisResult


def _make_article(title: str) -> Article:
    return Article(
        source="Test", title=title, content="Content",
        url="https://example.com",
        published_at=datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc),
    )


def _make_result(title: str, relevance: int) -> AnalysisResult:
    return AnalysisResult(
        title=title, source="Test", url="https://example.com",
        relevance=relevance, summary="summary", why_it_matters="matters",
    )


def test_main_orchestrates_pipeline_with_dedup():
    gmail_articles = [_make_article("Gmail Article")]
    rss_articles = [_make_article("RSS Article")]
    deduped = [_make_article("Merged Article")]
    analysis_results = [_make_result("Merged Article", 8)]

    with patch("main.read_gmail", return_value=gmail_articles), \
         patch("main.read_rss_feeds", return_value=rss_articles), \
         patch("main.deduplicate", return_value=deduped) as mock_dedup, \
         patch("main.analyze", return_value=analysis_results) as mock_analyze, \
         patch("main.send_report", return_value=True) as mock_send:
        import main
        main.main()

    mock_dedup.assert_called_once()
    mock_analyze.assert_called_once_with(deduped)
    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["total_analyzed"] == 1


def test_main_handles_empty_sources():
    with patch("main.read_gmail", return_value=[]), \
         patch("main.read_rss_feeds", return_value=[]), \
         patch("main.deduplicate", return_value=[]), \
         patch("main.analyze", return_value=[]) as mock_analyze, \
         patch("main.send_report", return_value=True) as mock_send:
        import main
        main.main()

    mock_analyze.assert_called_once_with([])
    assert mock_send.call_args.kwargs["total_analyzed"] == 0


def test_main_alerts_and_exits_on_crash():
    with patch("main.read_gmail", side_effect=Exception("boom")), \
         patch("main.send_alert") as mock_alert:
        import main
        with pytest.raises(SystemExit) as exc:
            main.main()

    assert exc.value.code == 1
    assert mock_alert.called


def test_main_exits_when_delivery_fails():
    with patch("main.read_gmail", return_value=[]), \
         patch("main.read_rss_feeds", return_value=[]), \
         patch("main.deduplicate", return_value=[]), \
         patch("main.analyze", return_value=[]), \
         patch("main.send_report", return_value=False):
        import main
        with pytest.raises(SystemExit) as exc:
            main.main()

    assert exc.value.code == 1
```

- [ ] **Step 2: Rodar para confirmar que falham**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL (main ainda não chama `deduplicate`/`send_alert`, nem usa exit codes)

- [ ] **Step 3: Implementar**

Substitua todo o conteúdo de `main.py` por:

```python
import logging
import os
import sys

from dotenv import load_dotenv

from src.analyzer import analyze
from src.deduplicator import deduplicate
from src.gmail_reader import read_gmail
from src.rss_reader import read_rss_feeds
from src.run_status import RunStatus
from src.telegram_sender import send_alert, send_report

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    status = RunStatus()
    try:
        label = os.getenv("GMAIL_LABEL", "newsletters")

        logger.info("Fetching Gmail newsletters (label: %s)...", label)
        gmail_articles = read_gmail(label, status=status)
        logger.info("Found %d Gmail articles", len(gmail_articles))

        logger.info("Fetching RSS feeds...")
        rss_articles = read_rss_feeds("config.yaml", status=status)
        logger.info("Found %d RSS articles", len(rss_articles))

        all_articles = gmail_articles + rss_articles
        if not all_articles:
            status.add("Nenhum conteúdo encontrado nas últimas 24h")

        logger.info("Deduplicating %d articles...", len(all_articles))
        deduped = deduplicate(all_articles, status=status)
        logger.info("After dedup: %d distinct items", len(deduped))

        results = analyze(deduped)
        logger.info("Analysis complete. Sending report...")

        delivered = send_report(
            results, total_analyzed=len(deduped), warnings=status.warnings
        )
        if not delivered:
            logger.error("Report delivery failed")
            sys.exit(1)

        logger.info("Done.")
    except Exception as e:
        logger.exception("Pipeline crashed")
        send_alert(f"🚨 Pipeline falhou: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

> Nota: `sys.exit(1)` lança `SystemExit`, que herda de `BaseException` (não de `Exception`), então o `except Exception` **não** captura o exit de falha de entrega — ele propaga limpo. Só crashes reais caem no `send_alert`.

- [ ] **Step 4: Rodar para confirmar que passam**

Run: `python -m pytest tests/test_main.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Rodar a suíte completa**

Run: `python -m pytest -v`
Expected: todos PASSED (suíte verde de ponta a ponta)

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: wire dedup + run-health alerting into main pipeline"
```

---

## Self-Review

**Cobertura do spec:**

| Requisito do spec | Task |
|---|---|
| `sources` em Article e AnalysisResult | Task 1 |
| `deduplicate` semântico via Haiku | Task 3 |
| Representante = maior conteúdo; fontes mescladas | Task 3 |
| Degradação graciosa da dedup + aviso | Task 3 |
| Analyzer propaga sources | Task 4 |
| Relatório "Visto em: A, B, C" | Task 5 |
| `RunStatus` acumulador | Task 2 |
| Readers reportam falha parcial | Task 7 |
| Rodapé `⚠️ Avisos` no relatório | Task 6 |
| Execução vazia ainda envia relatório + aviso | Task 8 |
| Crash → `send_alert` + exit(1) | Tasks 6, 8 |
| Falha de entrega → exit(1) | Tasks 6, 8 |
| Stateless (sem persistência) | Todas — só memória/API por run |

**Consistência de tipos:** `deduplicate(list[Article], RunStatus|None) -> list[Article]`; `RunStatus.add(str)`; `send_report(...) -> bool`; `send_alert(str) -> bool`; `format_report(..., warnings)`; readers com `status` opcional. Assinaturas batem entre as tasks que as consomem (Task 8 consome todas).

**Placeholder scan:** nenhum TBD/TODO; todo passo de código mostra o código completo.
