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
