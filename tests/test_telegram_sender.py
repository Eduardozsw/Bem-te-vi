from unittest.mock import patch, MagicMock
from src.telegram_sender import format_report, split_messages, send_report, send_alert
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
    assert "<b>" in report  # HTML bold, not Markdown


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
    payload = call_args[1]["json"]
    assert payload["parse_mode"] == "HTML"


def test_send_report_uses_html_parse_mode():
    results = [_make_result("News", 8)]

    with patch("requests.post") as mock_post, \
         patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "1"}):
        mock_post.return_value = MagicMock(ok=True)
        send_report(results, total_analyzed=1)

    payload = mock_post.call_args[1]["json"]
    assert payload["parse_mode"] == "HTML"
    assert "*" not in payload["text"]  # no raw Markdown bold in output


def test_format_report_multi_source_shows_visto_em():
    result = _make_result("Big news", 9)
    result.sources = ["TechCrunch", "HN", "Nord"]
    report = format_report([result], total_analyzed=1)
    assert "Visto em: TechCrunch, HN, Nord" in report
    assert "📌 Fonte:" not in report


def test_format_report_single_source_shows_fonte():
    result = _make_result("News", 9)
    result.sources = ["TechCrunch"]
    report = format_report([result], total_analyzed=1)
    assert "📌 Fonte: Test" in report  # usa result.source
    assert "Visto em:" not in report


def test_format_report_escapes_html_special_chars():
    """Titles with HTML-special chars (<, >, &, ") must be escaped to prevent broken HTML."""
    result = _make_result('Price cut <50% & "huge" impact > last year', 9)
    report = format_report([result], total_analyzed=1)
    # Raw HTML-special chars must not appear unescaped
    assert "<50%" not in report
    assert "&" not in report.replace("&amp;", "").replace("&lt;", "").replace("&gt;", "").replace("&quot;", "")
    # Escaped versions must be present
    assert "&lt;50%" in report
    assert "&amp;" in report
    assert "&gt;" in report
    # HTML bold must be used, not Markdown bold
    assert "<b>" in report
    assert f"*[9/10]" not in report


def test_format_report_with_warnings_shows_footer():
    result = _make_result("News", 8)
    report = format_report([result], total_analyzed=1, warnings=["Gmail: label não encontrada"])
    assert "Avisos" in report
    assert "Gmail: label não encontrada" in report


def test_format_report_without_warnings_no_footer():
    result = _make_result("News", 8)
    report = format_report([result], total_analyzed=1)
    assert "Avisos" not in report


def test_send_report_returns_true_on_success():
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1"}), \
         patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        ok = send_report([_make_result("N", 8)], total_analyzed=1)
    assert ok is True


def test_send_report_returns_false_on_api_failure():
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1"}), \
         patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=False, text="403 Forbidden")
        ok = send_report([_make_result("N", 8)], total_analyzed=1)
    assert ok is False


def test_send_report_returns_false_without_credentials():
    with patch.dict("os.environ", {}, clear=True):
        ok = send_report([_make_result("N", 8)], total_analyzed=1)
    assert ok is False


def test_send_alert_posts_and_returns_true():
    from src.telegram_sender import send_alert
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1"}), \
         patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        ok = send_alert("🚨 Pipeline falhou: boom")
    assert ok is True
    assert "sendMessage" in mock_post.call_args[0][0]


def test_send_alert_html_escapes_text():
    """send_alert must HTML-escape its text so Telegram's HTML parser doesn't reject it.

    Exception strings routinely contain <, >, and &. Without escaping, Telegram returns
    a 400 and the crash alert is never delivered. Emojis and the prefix survive html.escape
    unchanged, so the user-visible message is unaffected.
    """
    raw = "🚨 Pipeline falhou: KeyError <id> & stuff"
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1"}), \
         patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        send_alert(raw)

    posted_text = mock_post.call_args[1]["json"]["text"]
    # Raw HTML-special chars must not appear in the posted text
    assert "<id>" not in posted_text
    assert "& stuff" not in posted_text
    # Escaped versions must be present
    assert "&lt;id&gt;" in posted_text
    assert "&amp;" in posted_text
