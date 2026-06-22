from src.run_status import RunStatus


def test_runstatus_starts_empty():
    status = RunStatus()
    assert status.warnings == []


def test_runstatus_add_appends():
    status = RunStatus()
    status.add("Gmail: label não encontrada")
    status.add("RSS fora do ar")
    assert status.warnings == ["Gmail: label não encontrada", "RSS fora do ar"]
