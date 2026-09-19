import pytest
from unittest.mock import patch
from datetime import datetime, timezone
from src.models import Article, AnalysisResult


@pytest.fixture(autouse=True)
def mock_record_run():
    """Nenhum teste de main grava em data/runs.db de verdade."""
    with patch("main.record_run") as rr:
        yield rr


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
    rss_articles = [_make_article("RSS Article A"), _make_article("RSS Article B")]
    deduped = [_make_article("Merged Article")]
    analysis_results = [_make_result("Merged Article", 8)]

    with patch("main.read_rss_feeds", return_value=rss_articles), \
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
    with patch("main.read_rss_feeds", return_value=[]), \
         patch("main.deduplicate", return_value=[]), \
         patch("main.analyze", return_value=[]) as mock_analyze, \
         patch("main.send_report", return_value=True) as mock_send:
        import main
        main.main()

    mock_analyze.assert_called_once()
    assert mock_analyze.call_args.args[0] == []
    assert mock_send.call_args.kwargs["total_analyzed"] == 0


def test_main_alerts_and_exits_on_crash():
    with patch("main.read_rss_feeds", side_effect=Exception("boom")), \
         patch("main.send_alert") as mock_alert:
        import main
        with pytest.raises(SystemExit) as exc:
            main.main()

    assert exc.value.code == 1
    assert mock_alert.called


def test_main_exits_when_delivery_fails():
    with patch("main.read_rss_feeds", return_value=[]), \
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
    with patch.object(main_module, "read_rss_feeds", return_value=[]), \
         patch.object(main_module, "deduplicate", return_value=[]), \
         patch.object(main_module, "send_report", return_value=True), \
         patch.object(main_module, "load_profile", return_value={"projetos": {"X": {}}}) as lp, \
         patch.object(main_module, "analyze", return_value=[]) as az:
        main_module.main()
    lp.assert_called_once()
    assert az.call_args.kwargs.get("profile") == {"projetos": {"X": {}}} \
        or az.call_args.args[1] == {"projetos": {"X": {}}}


def _run_status_recorded(mock_record_run):
    mock_record_run.assert_called_once()
    return mock_record_run.call_args.kwargs["run_status"]


def test_main_records_success_run(mock_record_run):
    with patch("main.read_rss_feeds", return_value=[_make_article("A"), _make_article("B")]), \
         patch("main.deduplicate", return_value=[_make_article("A")]), \
         patch("main.load_profile", return_value={}), \
         patch("main.analyze", return_value=[_make_result("A", 8)]), \
         patch("main.send_report", return_value=True):
        import main
        main.main()

    assert _run_status_recorded(mock_record_run) == "success"
    status = mock_record_run.call_args.kwargs["status"]
    assert status.articles_collected == 2
    assert status.articles_after_dedup == 1


def test_main_records_partial_run_when_batches_fail(mock_record_run):
    def failing_analyze(articles, profile=None, status=None):
        status.batches_total, status.batches_failed = 2, 1
        status.add("Análise: 1 de 2 lotes falharam (5 artigos não analisados)")
        return []

    with patch("main.read_rss_feeds", return_value=[_make_article("A")]), \
         patch("main.deduplicate", return_value=[_make_article("A")]), \
         patch("main.load_profile", return_value={}), \
         patch("main.analyze", side_effect=failing_analyze), \
         patch("main.send_report", return_value=True) as mock_send:
        import main
        main.main()

    assert _run_status_recorded(mock_record_run) == "partial"
    assert "1 de 2 lotes falharam" in mock_send.call_args.kwargs["warnings"][0]


def test_main_records_failed_run_on_crash(mock_record_run):
    with patch("main.read_rss_feeds", side_effect=RuntimeError("boom")), \
         patch("main.send_alert"):
        import main
        with pytest.raises(SystemExit):
            main.main()

    assert _run_status_recorded(mock_record_run) == "failed"
    assert mock_record_run.call_args.kwargs["error"] == "RuntimeError: boom"


def test_main_records_failed_run_when_delivery_fails(mock_record_run):
    with patch("main.read_rss_feeds", return_value=[]), \
         patch("main.deduplicate", return_value=[]), \
         patch("main.analyze", return_value=[]), \
         patch("main.send_report", return_value=False):
        import main
        with pytest.raises(SystemExit):
            main.main()

    assert _run_status_recorded(mock_record_run) == "failed"
