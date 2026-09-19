from src.run_status import RunStatus


def test_runstatus_starts_empty():
    status = RunStatus()
    assert status.warnings == []


def test_runstatus_add_appends():
    status = RunStatus()
    status.add("RSS: config.yaml não encontrado")
    status.add("RSS fora do ar")
    assert status.warnings == ["RSS: config.yaml não encontrado", "RSS fora do ar"]


def test_record_usage_accumulates_tokens_and_cost():
    status = RunStatus()
    status.record_usage(100, 10, 0.5)
    status.record_usage(50, 5, 0.25)
    assert (status.prompt_tokens, status.completion_tokens) == (150, 15)
    assert status.total_cost_usd == 0.75


def test_total_cost_is_none_when_any_call_unpriced():
    status = RunStatus()
    status.record_usage(100, 10, 0.5)
    status.record_usage(50, 5, None)
    assert status.total_cost_usd is None
