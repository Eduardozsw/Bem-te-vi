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


def test_analysis_result_affects_defaults_empty():
    from src.models import AnalysisResult
    r = AnalysisResult(
        title="t", source="s", url="u", relevance=7,
        summary="sum", why_it_matters="why",
    )
    assert r.affects == []


def test_analysis_result_accepts_affects():
    from src.models import AnalysisResult
    r = AnalysisResult(
        title="t", source="s", url="u", relevance=7,
        summary="sum", why_it_matters="why", affects=["MindDoc"],
    )
    assert r.affects == ["MindDoc"]
