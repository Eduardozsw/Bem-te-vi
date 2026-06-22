# News Intelligence Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python pipeline that reads Gmail newsletters and RSS feeds, analyzes them with Claude Haiku, and sends a single daily report to Telegram via GitHub Actions.

**Architecture:** Linear pipeline — collect → analyze in batches of 10 → send report. No persistent state between runs. GitHub Actions triggers daily at 10h UTC.

**Tech Stack:** Python 3.11+, anthropic SDK, google-api-python-client, feedparser, requests, beautifulsoup4, pyyaml, python-dotenv, pytest

## Global Constraints

- Python 3.11+
- Model: `claude-haiku-4-5-20251001`
- Batch size: 10 articles per Claude call
- Relevance thresholds: ≥8 → 🔴, 6-7 → 🟡, ≤5 → ⚪ (ignored, shown as one-line summary)
- Telegram message limit: 4096 chars — split without breaking articles
- Gmail label: `newsletters` (hardcoded default, overridable via env)
- Time window: last 24h (calculated in UTC at runtime)
- All tests use `pytest`; mock all external API calls

---

### Task 1: Project scaffolding, dependencies, and data models

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `config.yaml`
- Create: `src/__init__.py`
- Create: `src/models.py`
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `Article(source: str, title: str, content: str, url: str, published_at: datetime)`
  - `AnalysisResult(title: str, source: str, url: str, relevance: int, summary: str, why_it_matters: str, impacts: list[str], actions: list[str])`

- [ ] **Step 1: Create `requirements.txt`**

```
anthropic>=0.40.0
google-auth>=2.0.0
google-auth-oauthlib>=1.0.0
google-api-python-client>=2.0.0
feedparser>=6.0.0
python-dotenv>=1.0.0
requests>=2.31.0
beautifulsoup4>=4.12.0
pyyaml>=6.0.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

- [ ] **Step 2: Create `.env.example`**

```
ANTHROPIC_API_KEY=your_anthropic_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
GMAIL_LABEL=newsletters
```

- [ ] **Step 3: Create `config.yaml`**

```yaml
rss_feeds:
  - name: "Hacker News"
    url: "https://news.ycombinator.com/rss"
  - name: "TechCrunch"
    url: "https://techcrunch.com/feed/"
```

- [ ] **Step 4: Create `src/__init__.py` and `tests/__init__.py`**

Both files are empty. Create them to make the directories Python packages.

- [ ] **Step 5: Write failing tests for models**

Create `tests/test_models.py`:

```python
from datetime import datetime, timezone
from src.models import Article, AnalysisResult


def test_article_fields():
    article = Article(
        source="Test Source",
        title="Test Title",
        content="Test content",
        url="https://example.com",
        published_at=datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc),
    )
    assert article.source == "Test Source"
    assert article.title == "Test Title"
    assert article.content == "Test content"
    assert article.url == "https://example.com"
    assert article.published_at.tzinfo is not None


def test_analysis_result_fields():
    result = AnalysisResult(
        title="Test Title",
        source="Test Source",
        url="https://example.com",
        relevance=8,
        summary="Short summary",
        why_it_matters="It matters because",
        impacts=["Impact 1", "Impact 2"],
        actions=["Action 1"],
    )
    assert result.relevance == 8
    assert len(result.impacts) == 2
    assert len(result.actions) == 1
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
cd C:\Users\dudus\Desktop\projetos\news-intelligence-assistant
python -m pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'src'`

- [ ] **Step 7: Create `src/models.py`**

```python
from dataclasses import dataclass, field
from datetime import datetime


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
    relevance: int
    summary: str
    why_it_matters: str
    impacts: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
```

- [ ] **Step 8: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 9: Run tests to verify they pass**

```bash
python -m pytest tests/test_models.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 10: Commit**

```bash
git init
git add requirements.txt .env.example config.yaml src/ tests/
git commit -m "feat: project scaffolding, models, and dependencies"
```

---

### Task 2: RSS reader

**Files:**
- Create: `src/rss_reader.py`
- Create: `tests/test_rss_reader.py`

**Interfaces:**
- Consumes: `Article` from `src.models`, `config.yaml` for feed list
- Produces: `read_rss_feeds(config_path: str) -> list[Article]`

- [ ] **Step 1: Write failing tests**

Create `tests/test_rss_reader.py`:

```python
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from src.rss_reader import read_rss_feeds
from src.models import Article


def _make_entry(title, url, published_parsed):
    entry = MagicMock()
    entry.title = title
    entry.link = url
    entry.summary = "Entry summary content"
    entry.published_parsed = published_parsed
    return entry


def test_returns_articles_within_24h(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("rss_feeds:\n  - name: Test\n    url: http://example.com/rss\n")

    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=12)).timetuple()
    old = (now - timedelta(hours=25)).timetuple()

    mock_feed = MagicMock()
    mock_feed.entries = [
        _make_entry("Recent article", "http://example.com/1", recent),
        _make_entry("Old article", "http://example.com/2", old),
    ]

    with patch("feedparser.parse", return_value=mock_feed):
        articles = read_rss_feeds(str(config_file))

    assert len(articles) == 1
    assert articles[0].title == "Recent article"
    assert articles[0].source == "Test"
    assert isinstance(articles[0], Article)


def test_returns_empty_when_no_recent_entries(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("rss_feeds:\n  - name: Test\n    url: http://example.com/rss\n")

    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=30)).timetuple()

    mock_feed = MagicMock()
    mock_feed.entries = [_make_entry("Old article", "http://example.com/1", old)]

    with patch("feedparser.parse", return_value=mock_feed):
        articles = read_rss_feeds(str(config_file))

    assert articles == []


def test_returns_empty_on_missing_config(tmp_path):
    articles = read_rss_feeds(str(tmp_path / "nonexistent.yaml"))
    assert articles == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_rss_reader.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.rss_reader'`

- [ ] **Step 3: Create `src/rss_reader.py`**

```python
import logging
from datetime import datetime, timezone, timedelta
from time import mktime

import feedparser
import yaml

from src.models import Article

logger = logging.getLogger(__name__)


def read_rss_feeds(config_path: str = "config.yaml") -> list[Article]:
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning("config.yaml not found at %s", config_path)
        return []

    feeds = config.get("rss_feeds", [])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    articles: list[Article] = []

    for feed_cfg in feeds:
        name = feed_cfg["name"]
        url = feed_cfg["url"]
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if not entry.get("published_parsed"):
                    continue
                published_at = datetime.fromtimestamp(
                    mktime(entry.published_parsed), tz=timezone.utc
                )
                if published_at < cutoff:
                    continue
                content = getattr(entry, "summary", "") or ""
                articles.append(
                    Article(
                        source=name,
                        title=entry.title,
                        content=content,
                        url=entry.link,
                        published_at=published_at,
                    )
                )
        except Exception as e:
            logger.error("Failed to fetch feed %s: %s", url, e)

    return articles
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_rss_reader.py -v
```

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/rss_reader.py tests/test_rss_reader.py
git commit -m "feat: RSS reader with 24h filter"
```

---

### Task 3: Gmail reader

**Files:**
- Create: `src/gmail_reader.py`
- Create: `setup_gmail_auth.py`
- Create: `tests/test_gmail_reader.py`

**Interfaces:**
- Consumes: `Article` from `src.models`; env vars `GMAIL_LABEL`, `GMAIL_TOKEN_JSON`, `GMAIL_CREDENTIALS_JSON`
- Produces: `read_gmail(label: str) -> list[Article]`

- [ ] **Step 1: Write failing tests**

Create `tests/test_gmail_reader.py`:

```python
import base64
import json
from unittest.mock import patch, MagicMock
from src.gmail_reader import extract_body, read_gmail
from src.models import Article


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_extract_body_prefers_plain_text():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64("Plain text content")}},
            {"mimeType": "text/html", "body": {"data": _b64("<p>HTML content</p>")}},
        ],
    }
    assert extract_body(payload) == "Plain text content"


def test_extract_body_falls_back_to_html():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "text/html", "body": {"data": _b64("<p>HTML only</p>")}},
        ],
    }
    result = extract_body(payload)
    assert "HTML only" in result


def test_extract_body_simple_plain():
    payload = {
        "mimeType": "text/plain",
        "body": {"data": _b64("Simple plain text")},
    }
    assert extract_body(payload) == "Simple plain text"


def test_read_gmail_returns_articles():
    mock_service = MagicMock()

    mock_service.users().labels().list().execute.return_value = {
        "labels": [{"id": "Label_123", "name": "newsletters"}]
    }
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg1"}]
    }
    mock_service.users().messages().get().execute.return_value = {
        "id": "msg1",
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": _b64("Newsletter content")},
            "headers": [
                {"name": "Subject", "value": "Weekly Newsletter"},
                {"name": "From", "value": "editor@example.com"},
                {"name": "Date", "value": "Fri, 20 Jun 2026 08:00:00 +0000"},
            ],
        },
    }

    with patch("src.gmail_reader._build_service", return_value=mock_service):
        articles = read_gmail("newsletters")

    assert len(articles) == 1
    assert articles[0].title == "Weekly Newsletter"
    assert articles[0].source == "editor@example.com"
    assert "Newsletter content" in articles[0].content
    assert isinstance(articles[0], Article)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_gmail_reader.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.gmail_reader'`

- [ ] **Step 3: Create `src/gmail_reader.py`**

```python
import base64
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.models import Article

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _build_service():
    token_json = os.getenv("GMAIL_TOKEN_JSON")
    if token_json:
        token_data = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    else:
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            with open("token.json", "w") as f:
                f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def extract_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)

    parts = payload.get("parts", [])
    plain = next((p for p in parts if p.get("mimeType") == "text/plain"), None)
    if plain:
        return extract_body(plain)
    html_part = next((p for p in parts if p.get("mimeType") == "text/html"), None)
    if html_part:
        return extract_body(html_part)
    for part in parts:
        result = extract_body(part)
        if result:
            return result
    return ""


def _get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def read_gmail(label: str = "newsletters") -> list[Article]:
    try:
        service = _build_service()
    except Exception as e:
        logger.error("Failed to build Gmail service: %s", e)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    try:
        labels_response = service.users().labels().list(userId="me").execute()
        label_id = next(
            (l["id"] for l in labels_response.get("labels", []) if l["name"] == label),
            None,
        )
        if not label_id:
            logger.warning("Gmail label '%s' not found", label)
            return []

        messages_response = (
            service.users()
            .messages()
            .list(userId="me", labelIds=[label_id], maxResults=50)
            .execute()
        )
        messages = messages_response.get("messages", [])
    except Exception as e:
        logger.error("Failed to list Gmail messages: %s", e)
        return []

    articles: list[Article] = []
    for msg in messages:
        try:
            full = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()
            payload = full["payload"]
            headers = payload.get("headers", [])

            date_str = _get_header(headers, "Date")
            try:
                published_at = parsedate_to_datetime(date_str).astimezone(timezone.utc)
            except Exception:
                continue

            if published_at < cutoff:
                continue

            subject = _get_header(headers, "Subject") or "(sem assunto)"
            sender = _get_header(headers, "From")
            body = extract_body(payload)

            articles.append(
                Article(
                    source=sender,
                    title=subject,
                    content=body[:5000],
                    url="",
                    published_at=published_at,
                )
            )
        except Exception as e:
            logger.error("Failed to process message %s: %s", msg["id"], e)

    return articles
```

- [ ] **Step 4: Create `setup_gmail_auth.py`**

```python
"""Run this script once locally to generate token.json for Gmail OAuth."""
from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token.json", "w") as f:
    f.write(creds.to_json())

print("token.json created successfully.")
print("\nCopy the contents below to the GMAIL_TOKEN_JSON GitHub secret:\n")
print(creds.to_json())
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_gmail_reader.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add src/gmail_reader.py setup_gmail_auth.py tests/test_gmail_reader.py
git commit -m "feat: Gmail reader with OAuth2 and body extraction"
```

---

### Task 4: Analyzer (Claude Haiku + batching)

**Files:**
- Create: `src/analyzer.py`
- Create: `tests/test_analyzer.py`

**Interfaces:**
- Consumes: `list[Article]` from `src.models`; env var `ANTHROPIC_API_KEY`
- Produces: `analyze(articles: list[Article]) -> list[AnalysisResult]`

- [ ] **Step 1: Write failing tests**

Create `tests/test_analyzer.py`:

```python
import json
from unittest.mock import patch, MagicMock
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

    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(
            text=json.dumps([
                {
                    "title": "OpenAI cuts API prices by 80%",
                    "relevance": 9,
                    "summary": "Major price cut for GPT APIs",
                    "why_it_matters": "Reduces AI project costs significantly",
                    "impacts": ["Cheaper AI projects", "More competition"],
                    "actions": ["Review current API costs"],
                }
            ])
        )
    ]

    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

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

    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API error")

        results = analyze(articles)

    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_analyzer.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.analyzer'`

- [ ] **Step 3: Create `src/analyzer.py`**

```python
import json
import logging
import os

import anthropic

from src.models import Article, AnalysisResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a personal news intelligence assistant. Your job is to analyze articles and rate their relevance for a tech/finance professional interested in practical applications.

PRIORITIZE (high score 7-10):
- Cost reductions in technology or tools
- New technologies with immediate practical application
- Concrete business opportunities
- Automation and productivity gains
- Applied AI (not theoretical benchmarks)
- Impactful Data Science developments
- Relevant open source releases
- Regulatory changes with direct impact

DEPRIORITIZE (low score 0-5):
- Benchmarks without practical impact
- Corporate marketing and announcements
- Minor incremental improvements
- Discussions without practical consequences

You will receive a JSON array of articles. Return a JSON array with one result per article (same order), following this exact schema:
[
  {
    "title": "<article title>",
    "relevance": <integer 0-10>,
    "summary": "<2-3 word summary for low-relevance items, 1-2 sentences for high-relevance>",
    "why_it_matters": "<one sentence explaining why this matters>",
    "impacts": ["<impact 1>", "<impact 2>"],
    "actions": ["<possible action 1>"]
  }
]

For low-relevance items (score ≤ 5), keep summary very short (2-4 words). For high-relevance items (score ≥ 6), provide full analysis.
Return ONLY the JSON array. No markdown, no explanation."""


def _build_batches(articles: list[Article], batch_size: int = 10) -> list[list[Article]]:
    return [articles[i : i + batch_size] for i in range(0, len(articles), batch_size)]


def _parse_response(text: str, batch: list[Article]) -> list[AnalysisResult]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            raise
        data = json.loads(text[start:end])

    results = []
    for i, item in enumerate(data):
        article = batch[i] if i < len(batch) else batch[-1]
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
            )
        )
    return results


def analyze(articles: list[Article]) -> list[AnalysisResult]:
    if not articles:
        return []

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    batches = _build_batches(articles, batch_size=10)
    all_results: list[AnalysisResult] = []

    for batch in batches:
        payload = [
            {"title": a.title, "source": a.source, "content": a.content[:2000]}
            for a in batch
        ]
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
                ],
            )
            results = _parse_response(response.content[0].text, batch)
            all_results.extend(results)
        except Exception as e:
            logger.error("Analyzer batch failed: %s", e)

    return all_results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_analyzer.py -v
```

Expected: 5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/analyzer.py tests/test_analyzer.py
git commit -m "feat: Claude Haiku analyzer with batching and prompt caching"
```

---

### Task 5: Telegram sender

**Files:**
- Create: `src/telegram_sender.py`
- Create: `tests/test_telegram_sender.py`

**Interfaces:**
- Consumes: `list[AnalysisResult]` from `src.models`; env vars `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Produces: `send_report(results: list[AnalysisResult], total_analyzed: int) -> None`

- [ ] **Step 1: Write failing tests**

Create `tests/test_telegram_sender.py`:

```python
from unittest.mock import patch, MagicMock
from src.telegram_sender import format_report, split_messages, send_report
from src.models import AnalysisResult


def _make_result(title: str, relevance: int, source: str = "Test") -> AnalysisResult:
    return AnalysisResult(
        title=title,
        source=source,
        url="https://example.com",
        relevance=relevance,
        summary="Short summary of " + title,
        why_it_matters="It matters because of reasons",
        impacts=["Impact 1"],
        actions=["Action 1"],
    )


def test_format_report_contains_header():
    results = [_make_result("Big AI news", 9)]
    report = format_report(results, total_analyzed=5)
    assert "Inteligência Diária" in report
    assert "Analisados: 5" in report


def test_format_report_red_high_relevance():
    results = [_make_result("Critical news", 8)]
    report = format_report(results, total_analyzed=1)
    assert "🔴" in report
    assert "[8/10]" in report
    assert "Critical news" in report


def test_format_report_yellow_medium_relevance():
    results = [_make_result("Medium news", 6)]
    report = format_report(results, total_analyzed=1)
    assert "🟡" in report
    assert "[6/10]" in report


def test_format_report_ignored_shown_as_oneliner():
    results = [_make_result("Boring benchmark", 3)]
    report = format_report(results, total_analyzed=1)
    assert "⚪" in report
    assert "Ignorados" in report
    assert "Boring benchmark" in report
    assert "Impact 1" not in report  # no detailed analysis for ignored


def test_format_report_mixed():
    results = [
        _make_result("High news", 9),
        _make_result("Medium news", 7),
        _make_result("Low news", 2),
    ]
    report = format_report(results, total_analyzed=3)
    assert "🔴" in report
    assert "🟡" in report
    assert "⚪" in report


def test_split_messages_under_limit():
    short_message = "A" * 100
    parts = split_messages(short_message)
    assert len(parts) == 1
    assert parts[0] == short_message


def test_split_messages_over_limit():
    separator = "━" * 20
    block = separator + "\nArticle content here\n"
    long_message = block * 30  # well over 4096 chars
    parts = split_messages(long_message)
    assert len(parts) > 1
    for part in parts:
        assert len(part) <= 4096


def test_send_report_calls_telegram_api():
    results = [_make_result("News", 8)]

    with patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        send_report(results, total_analyzed=1)

    assert mock_post.called
    call_args = mock_post.call_args
    assert "sendMessage" in call_args[0][0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_telegram_sender.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.telegram_sender'`

- [ ] **Step 3: Create `src/telegram_sender.py`**

```python
import logging
import os
from datetime import datetime, timezone

import requests

from src.models import AnalysisResult

logger = logging.getLogger(__name__)

SEPARATOR = "━" * 22
TELEGRAM_LIMIT = 4096


def format_report(results: list[AnalysisResult], total_analyzed: int) -> str:
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    important = [r for r in results if r.relevance >= 6]
    ignored = [r for r in results if r.relevance <= 5]

    lines = [
        f"📊 *Inteligência Diária — {today}*\n",
        f"Analisados: {total_analyzed} conteúdos | Importantes: {len(important)} | Ignorados: {len(ignored)}",
    ]

    for result in sorted(important, key=lambda r: r.relevance, reverse=True):
        emoji = "🔴" if result.relevance >= 8 else "🟡"
        block = [
            f"\n{SEPARATOR}",
            f"{emoji} *[{result.relevance}/10] {result.title}*",
            f"📌 Fonte: {result.source}",
            f"\n{result.summary}",
            f"\nPor que importa: {result.why_it_matters}",
        ]
        if result.impacts:
            block.append("\nImpactos:")
            block.extend(f"• {impact}" for impact in result.impacts)
        if result.actions:
            block.append("\nAções possíveis:")
            block.extend(f"• {action}" for action in result.actions)
        lines.extend(block)

    if ignored:
        lines.append(f"\n{SEPARATOR}")
        lines.append(f"⚪ *Ignorados ({len(ignored)})*\n")
        for result in ignored:
            lines.append(f"• {result.summary or result.title} — {result.source}")

    return "\n".join(lines)


def split_messages(text: str) -> list[str]:
    if len(text) <= TELEGRAM_LIMIT:
        return [text]

    parts = []
    current = ""
    for block in text.split(SEPARATOR):
        chunk = (SEPARATOR + block) if current else block
        if len(current) + len(chunk) > TELEGRAM_LIMIT:
            if current:
                parts.append(current.strip())
            current = chunk
        else:
            current += chunk
    if current.strip():
        parts.append(current.strip())
    return parts


def send_report(results: list[AnalysisResult], total_analyzed: int) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return

    report = format_report(results, total_analyzed)
    messages = split_messages(report)
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for message in messages:
        try:
            response = requests.post(
                url,
                json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
                timeout=10,
            )
            if not response.ok:
                logger.error("Telegram API error: %s", response.text)
        except Exception as e:
            logger.error("Failed to send Telegram message: %s", e)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_telegram_sender.py -v
```

Expected: 8 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/telegram_sender.py tests/test_telegram_sender.py
git commit -m "feat: Telegram sender with report formatting and message splitting"
```

---

### Task 6: Main pipeline entrypoint

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

**Interfaces:**
- Consumes:
  - `read_rss_feeds(config_path: str) -> list[Article]` from `src.rss_reader`
  - `read_gmail(label: str) -> list[Article]` from `src.gmail_reader`
  - `analyze(articles: list[Article]) -> list[AnalysisResult]` from `src.analyzer`
  - `send_report(results: list[AnalysisResult], total_analyzed: int) -> None` from `src.telegram_sender`
  - env var `GMAIL_LABEL` (default: `newsletters`)
- Produces: pipeline orchestrator, `main()` function

- [ ] **Step 1: Write failing tests**

Create `tests/test_main.py`:

```python
from unittest.mock import patch, MagicMock
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
        impacts=[], actions=[],
    )


def test_main_orchestrates_pipeline():
    gmail_articles = [_make_article("Gmail Article")]
    rss_articles = [_make_article("RSS Article")]
    all_articles = gmail_articles + rss_articles
    analysis_results = [_make_result("Gmail Article", 8), _make_result("RSS Article", 4)]

    with patch("main.read_gmail", return_value=gmail_articles) as mock_gmail, \
         patch("main.read_rss_feeds", return_value=rss_articles) as mock_rss, \
         patch("main.analyze", return_value=analysis_results) as mock_analyze, \
         patch("main.send_report") as mock_send:

        import main
        main.main()

    mock_gmail.assert_called_once()
    mock_rss.assert_called_once()
    mock_analyze.assert_called_once_with(all_articles)
    mock_send.assert_called_once_with(analysis_results, total_analyzed=2)


def test_main_handles_empty_sources():
    with patch("main.read_gmail", return_value=[]), \
         patch("main.read_rss_feeds", return_value=[]), \
         patch("main.analyze", return_value=[]) as mock_analyze, \
         patch("main.send_report") as mock_send:

        import main
        main.main()

    mock_analyze.assert_called_once_with([])
    mock_send.assert_called_once_with([], total_analyzed=0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_main.py -v
```

Expected: `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Create `main.py`**

```python
import logging
import os

from dotenv import load_dotenv

from src.analyzer import analyze
from src.gmail_reader import read_gmail
from src.rss_reader import read_rss_feeds
from src.telegram_sender import send_report

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    label = os.getenv("GMAIL_LABEL", "newsletters")

    logger.info("Fetching Gmail newsletters (label: %s)...", label)
    gmail_articles = read_gmail(label)
    logger.info("Found %d Gmail articles", len(gmail_articles))

    logger.info("Fetching RSS feeds...")
    rss_articles = read_rss_feeds("config.yaml")
    logger.info("Found %d RSS articles", len(rss_articles))

    all_articles = gmail_articles + rss_articles
    logger.info("Total articles to analyze: %d", len(all_articles))

    results = analyze(all_articles)
    logger.info("Analysis complete. Sending report...")

    send_report(results, total_analyzed=len(all_articles))
    logger.info("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_main.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest -v
```

Expected: all tests PASSED

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: main pipeline entrypoint"
```

---

### Task 7: GitHub Actions workflow and project config files

**Files:**
- Create: `.github/workflows/daily.yml`
- Create: `.gitignore`

**Interfaces:**
- Consumes: GitHub Secrets — `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GMAIL_TOKEN_JSON`, `GMAIL_CREDENTIALS_JSON`
- Produces: scheduled daily workflow, project ignore rules

- [ ] **Step 1: Create `.gitignore`**

```
.env
token.json
credentials.json
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
.venv/
venv/
```

- [ ] **Step 2: Create `.github/workflows/daily.yml`**

```yaml
name: Daily News Intelligence

on:
  schedule:
    - cron: "0 10 * * *"  # 10h UTC = 7h BRT
  workflow_dispatch:       # manual trigger for testing

jobs:
  run-pipeline:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Reconstruct Gmail auth files
        env:
          GMAIL_TOKEN_JSON: ${{ secrets.GMAIL_TOKEN_JSON }}
          GMAIL_CREDENTIALS_JSON: ${{ secrets.GMAIL_CREDENTIALS_JSON }}
        run: |
          echo "$GMAIL_CREDENTIALS_JSON" > credentials.json

      - name: Run pipeline
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GMAIL_TOKEN_JSON: ${{ secrets.GMAIL_TOKEN_JSON }}
          GMAIL_LABEL: newsletters
        run: python main.py
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore .github/
git commit -m "feat: GitHub Actions daily workflow"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Gmail OAuth 2.0 | Task 3 |
| Gmail label-based filtering | Task 3 |
| RSS feeds from config.yaml | Task 2 |
| Claude Haiku analysis with batching | Task 4 |
| Prompt caching | Task 4 (`cache_control`) |
| Relevance criteria (prioritize/deprioritize) | Task 4 (SYSTEM_PROMPT) |
| Telegram report with 🔴🟡⚪ | Task 5 |
| Ignored items as one-liners | Task 5 |
| Message splitting at 4096 chars | Task 5 |
| GitHub Actions daily at 10h UTC | Task 7 |
| Secrets reconstruction | Task 7 |
| setup_gmail_auth.py for initial setup | Task 3 |
| .env / .env.example | Task 1 |
| requirements.txt | Task 1 |
| Logging | Task 6 |
| .gitignore (excludes token.json, credentials.json) | Task 7 |

All spec requirements are covered.

**Type consistency check:** All tasks use `Article` and `AnalysisResult` from `src.models` consistently. `read_gmail` and `read_rss_feeds` both return `list[Article]`. `analyze` consumes `list[Article]` and returns `list[AnalysisResult]`. `send_report` consumes `list[AnalysisResult]`. Signatures are consistent across all task interfaces.
