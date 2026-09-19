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


def test_empty_profile_leaves_prompt_unchanged_and_affects_empty():
    from src.analyzer import SYSTEM_PROMPT
    articles = [_make_article("Some news")]
    payload = json.dumps([
        {"title": "Some news", "relevance": 7, "summary": "s",
         "why_it_matters": "w", "impacts": [], "actions": []}
    ])
    captured = {}

    def fake_complete(system, user, max_tokens=4096, **kwargs):
        captured["system"] = system
        return payload

    with patch("src.analyzer.complete", side_effect=fake_complete):
        results = analyze(articles, profile={})

    assert captured["system"] == SYSTEM_PROMPT
    assert results[0].affects == []


def test_profile_is_injected_into_system_prompt():
    articles = [_make_article("Qwen 3B beats Llama 8B")]
    payload = json.dumps([
        {"title": "Qwen 3B beats Llama 8B", "relevance": 8, "summary": "s",
         "why_it_matters": "w", "impacts": [], "actions": [], "affects": ["MindDoc"]}
    ])
    captured = {}

    def fake_complete(system, user, max_tokens=4096, **kwargs):
        captured["system"] = system
        return payload

    profile = {"projetos": {"MindDoc": {"stack": "LLMs locais"}}}
    with patch("src.analyzer.complete", side_effect=fake_complete):
        results = analyze(articles, profile=profile)

    assert "MindDoc" in captured["system"]
    assert results[0].affects == ["MindDoc"]


def test_affects_defaults_empty_when_model_omits_it():
    articles = [_make_article("News")]
    payload = json.dumps([
        {"title": "News", "relevance": 7, "summary": "s",
         "why_it_matters": "w", "impacts": [], "actions": []}
    ])
    with patch("src.analyzer.complete", return_value=payload):
        results = analyze(articles, profile={"projetos": {"X": {}}})
    assert results[0].affects == []


def test_profile_adds_affects_to_schema():
    articles = [_make_article("Some local model news")]
    payload = json.dumps([
        {"title": "Some local model news", "relevance": 8, "summary": "s",
         "why_it_matters": "w", "impacts": [], "actions": [], "affects": ["Bem-te-vi"]}
    ])
    captured = {}

    def fake_complete(system, user, max_tokens=4096, **kwargs):
        captured["system"] = system
        return payload

    profile = {"projetos": {"Bem-te-vi": {"o_que_me_importa": "modelos locais"}}}
    with patch("src.analyzer.complete", side_effect=fake_complete):
        results = analyze(articles, profile=profile)

    system = captured["system"]
    assert '"affects"' in system
    # affects must be in the JSON schema example, before the profile context block
    assert system.index('"affects"') < system.index("USER PROFILE")
    assert results[0].affects == ["Bem-te-vi"]


def _ok_payload(titles):
    return json.dumps([
        {"title": t, "relevance": 7, "summary": "s",
         "why_it_matters": "w", "impacts": [], "actions": []}
        for t in titles
    ])


def test_analyze_reports_failed_batches_in_status():
    from src.run_status import RunStatus
    articles = [_make_article(f"Article {i}") for i in range(15)]  # 2 lotes: 10 + 5
    ok = _ok_payload([f"Article {i}" for i in range(10)])
    status = RunStatus()
    with patch("src.analyzer.complete", side_effect=[ok, Exception("timeout")]):
        results = analyze(articles, status=status)

    assert len(results) == 10  # lote bom preservado
    assert status.batches_total == 2
    assert status.batches_failed == 1
    assert status.warnings == ["Análise: 1 de 2 lotes falharam (5 artigos não analisados)"]


def test_analyze_no_warning_when_all_batches_succeed():
    from src.run_status import RunStatus
    articles = [_make_article("Only")]
    status = RunStatus()
    with patch("src.analyzer.complete", return_value=_ok_payload(["Only"])):
        analyze(articles, status=status)
    assert status.batches_total == 1
    assert status.batches_failed == 0
    assert status.warnings == []


def test_analyze_failure_without_status_does_not_raise():
    articles = [_make_article("Only")]
    with patch("src.analyzer.complete", side_effect=Exception("boom")):
        assert analyze(articles, status=None) == []


def test_analyze_ignores_text_after_the_json():
    from src.run_status import RunStatus
    articles = [_make_article("A"), _make_article("B")]
    response = _ok_payload(["A", "B"]) + "\n\nNote: [B] is less relevant."
    status = RunStatus()
    with patch("src.analyzer.complete", return_value=response):
        results = analyze(articles, status=status)

    assert [r.title for r in results] == ["A", "B"]
    assert status.batches_failed == 0


def test_analyze_truncated_response_keeps_complete_items():
    from src.run_status import RunStatus
    articles = [_make_article(t) for t in "ABC"]
    full = _ok_payload(["A", "B", "C"])
    truncated = full[: full.index('"C"') + 5]  # cortado no meio do 3º objeto
    status = RunStatus()
    with patch("src.analyzer.complete", return_value=truncated):
        results = analyze(articles, status=status)

    assert [r.title for r in results] == ["A", "B"]
    assert status.batches_failed == 0
