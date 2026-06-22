import json
import logging

from src.llm import complete
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

LANGUAGE: Always write the "summary", "why_it_matters", "impacts", and "actions" fields in Brazilian Portuguese (pt-BR), regardless of the article's original language. Keep the "title" field in the article's original language.
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

    if len(data) != len(batch):
        logger.warning(
            "LLM returned %d results for batch of %d articles; truncating/padding",
            len(data), len(batch),
        )

    results = []
    for i, item in enumerate(data):
        if i >= len(batch):
            break  # never mis-attribute extras
        article = batch[i]
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
    return results


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
