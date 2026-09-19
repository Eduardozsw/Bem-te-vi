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


def test_format_report_yellow_for_seven():
    results = [_make_result("Medium news", 7)]
    report = format_report(results, total_analyzed=1)
    assert "🟡" in report
    assert "[7/10]" in report


def test_format_report_below_cut_is_only_counted():
    results = [_make_result("Boring benchmark", 3), _make_result("Meh news", 6)]
    report = format_report(results, total_analyzed=2)
    assert "Abaixo de 7/10: 2" in report
    assert "Boring benchmark" not in report
    assert "Meh news" not in report
    assert "Ignorados" not in report


def test_format_report_says_so_when_nothing_relevant():
    report = format_report([_make_result("Meh", 5)], total_analyzed=1)
    assert "Nada acima de 7/10 hoje" in report
    assert "Destaques: 0" in report


def test_format_report_no_empty_notice_when_there_are_highlights():
    report = format_report([_make_result("Big", 9)], total_analyzed=1)
    assert "Nada acima" not in report


def test_format_report_mixed():
    results = [
        _make_result("High news", 9),
        _make_result("Medium news", 7),
        _make_result("Low news", 2),
    ]
    report = format_report(results, total_analyzed=3)
    assert "🔴" in report
    assert "🟡" in report
    assert "Low news" not in report
    assert "Destaques: 2 | Abaixo de 7/10: 1" in report


def test_format_report_title_links_to_article():
    r = _make_result("Linked news", 8)
    r.url = "https://example.com/a?x=1&y=2"
    report = format_report([r], total_analyzed=1)
    assert '<a href="https://example.com/a?x=1&amp;y=2">Linked news</a>' in report


def test_format_report_title_without_url_is_plain_text():
    r = _make_result("No link", 8)
    r.url = ""
    report = format_report([r], total_analyzed=1)
    assert "<a " not in report
    assert "No link" in report


def test_format_report_caps_highlights_and_lists_overflow_compactly():
    results = [_make_result(f"News {i}", 9 if i < 3 else 7) for i in range(8)]
    report = format_report(results, total_analyzed=8)
    assert "Destaques: 5" in report
    assert report.count("Por que importa") == 5
    assert "Também relevantes (3)" in report
    assert report.count("Impact 1") == 5  # itens compactos não têm análise completa


def test_format_report_highlights_are_highest_scores_first():
    results = [_make_result("Low7", 7), _make_result("Top10", 10), _make_result("Mid8", 8)]
    report = format_report(results, total_analyzed=3)
    assert report.index("Top10") < report.index("Mid8") < report.index("Low7")


def test_format_report_overflow_list_is_capped():
    results = [_make_result(f"News {i}", 8) for i in range(20)]
    report = format_report(results, total_analyzed=20)
    assert "Também relevantes (15)" in report
    assert "… e mais 5" in report


def test_format_report_thresholds_from_env():
    results = [_make_result("Six", 6), _make_result("Nine", 9), _make_result("Eight", 8)]
    env = {"REPORT_MIN_RELEVANCE": "6", "REPORT_MAX_HIGHLIGHTS": "1"}
    with patch.dict("os.environ", env):
        report = format_report(results, total_analyzed=3)
    assert "Destaques: 1 | Abaixo de 6/10: 0" in report
    assert "Também relevantes (2)" in report


def test_format_report_invalid_env_falls_back_to_default():
    with patch.dict("os.environ", {"REPORT_MIN_RELEVANCE": "alto"}):
        report = format_report([_make_result("Six", 6)], total_analyzed=1)
    assert "Abaixo de 7/10: 1" in report


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
    assert payload["link_preview_options"] == {"is_disabled": True}
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


def test_format_report_renders_affects_tag():
    from src.models import AnalysisResult
    from src.telegram_sender import format_report
    r = AnalysisResult(
        title="Qwen 3B", source="HN", url="u", relevance=8,
        summary="s", why_it_matters="w", affects=["MindDoc", "Cripto"],
    )
    report = format_report([r], total_analyzed=1)
    assert "🏷️ Afeta: MindDoc, Cripto" in report


def test_format_report_omits_tag_when_no_affects():
    from src.models import AnalysisResult
    from src.telegram_sender import format_report
    r = AnalysisResult(
        title="Generic", source="HN", url="u", relevance=8,
        summary="s", why_it_matters="w",
    )
    report = format_report([r], total_analyzed=1)
    assert "Afeta:" not in report
