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
