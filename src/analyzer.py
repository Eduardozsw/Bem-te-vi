import json
import logging
import yaml

from src.llm import complete
from src.llm_json import extract_json_list
from src.models import Article, AnalysisResult
from src.run_status import RunStatus

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


def _profile_block(profile: dict) -> str:
    if not profile:
        return ""
    rendered = yaml.safe_dump(profile, allow_unicode=True, sort_keys=False)
    return (
        "\n\nUSER PROFILE: The reader has the following projects/assets/interests. "
        "When an article is relevant to a NAMED item below, put that exact name in "
        "the \"affects\" array and write \"why_it_matters\"/\"actions\" from the "
        "perspective of that item. If nothing applies, leave \"affects\" empty.\n"
        f"{rendered}"
        "\n\nFor each result object, add an \"affects\" field (array of strings) listing "
        "the exact names from the profile above that this article touches. Use an empty "
        "array if none apply."
    )


def _system_prompt(profile: dict) -> str:
    if not profile:
        return SYSTEM_PROMPT
    schema = SYSTEM_PROMPT.replace(
        '    "actions": ["<possible action 1>"]',
        '    "actions": ["<possible action 1>"],\n'
        '    "affects": ["<exact names from the user profile this item touches; [] if none>"]',
    )
    return schema + _profile_block(profile)


def _build_batches(articles: list[Article], batch_size: int = 10) -> list[list[Article]]:
    return [articles[i : i + batch_size] for i in range(0, len(articles), batch_size)]


def _parse_response(text: str, batch: list[Article]) -> list[AnalysisResult]:
    data = extract_json_list(text, dict)

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
                affects=item.get("affects", []) or [],
            )
        )
    return results


def analyze(
    articles: list[Article],
    profile: dict | None = None,
    status: RunStatus | None = None,
) -> list[AnalysisResult]:
    if not articles:
        return []

    system_prompt = _system_prompt(profile or {})
    batches = _build_batches(articles, batch_size=10)
    all_results: list[AnalysisResult] = []
    failed_batches = 0
    lost_articles = 0

    for i, batch in enumerate(batches, start=1):
        payload = [
            {"title": a.title, "source": a.source, "content": a.content[:2000]}
            for a in batch
        ]
        text = ""
        try:
            text = complete(
                system_prompt,
                json.dumps(payload, ensure_ascii=False),
                max_tokens=4096,
                status=status,
            )
            results = _parse_response(text, batch)
            all_results.extend(results)
        except Exception as e:
            failed_batches += 1
            lost_articles += len(batch)
            logger.error(
                "Analyzer batch %d/%d failed: %s (response start: %r)",
                i, len(batches), e, text[:300],
            )

    if status is not None:
        status.batches_total += len(batches)
        status.batches_failed += failed_batches
        if failed_batches:
            status.add(
                f"Análise: {failed_batches} de {len(batches)} lotes falharam "
                f"({lost_articles} artigos não analisados)"
            )

    return all_results
