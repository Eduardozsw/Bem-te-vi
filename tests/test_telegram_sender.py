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
    separator = "━" * 22
    block = separator + "\nArticle content here\n"
    long_message = block * 100  # well over 4096 chars
    parts = split_messages(long_message)
    assert len(parts) > 1
    for part in parts:
        assert len(part) <= 4096


def test_send_report_calls_telegram_api():
    results = [_make_result("News", 8)]

    with patch("requests.post") as mock_post, \
         patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "123"}):
        mock_post.return_value = MagicMock(ok=True)
        send_report(results, total_analyzed=1)

    assert mock_post.called
    call_args = mock_post.call_args
    assert "sendMessage" in call_args[0][0]
