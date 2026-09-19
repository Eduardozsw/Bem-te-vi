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
    mock_analyze.assert_called_once()
    assert mock_analyze.call_args.args[0] == deduped
    assert mock_analyze.call_args.kwargs["status"] is not None
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

    mock_analyze.assert_called_once()
    assert mock_analyze.call_args.args[0] == []
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


def test_main_loads_profile_and_passes_to_analyze():
    from unittest.mock import patch, MagicMock
    import main as main_module
    with patch.object(main_module, "read_gmail", return_value=[]), \
         patch.object(main_module, "read_rss_feeds", return_value=[]), \
         patch.object(main_module, "deduplicate", return_value=[]), \
         patch.object(main_module, "send_report", return_value=True), \
         patch.object(main_module, "load_profile", return_value={"projetos": {"X": {}}}) as lp, \
         patch.object(main_module, "analyze", return_value=[]) as az:
        main_module.main()
    lp.assert_called_once()
    assert az.call_args.kwargs.get("profile") == {"projetos": {"X": {}}} \
        or az.call_args.args[1] == {"projetos": {"X": {}}}
