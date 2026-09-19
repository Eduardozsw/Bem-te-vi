import json
import logging

from src.llm import complete
from src.llm_json import extract_json_list
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
    data = extract_json_list(text, list)

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
    text = ""
    try:
        text = complete(
            DEDUP_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            max_tokens=2048,
            status=status,
        )
        groups = _parse_groups(text, len(articles))
    except Exception as e:
        logger.error(
            "Deduplication failed, falling back to no-dedup: %s (response start: %r)",
            e, text[:300],
        )
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
