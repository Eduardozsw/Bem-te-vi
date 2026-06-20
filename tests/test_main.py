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
