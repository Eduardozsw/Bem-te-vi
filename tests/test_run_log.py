import json
import sqlite3
from datetime import datetime, timezone

import pytest

from src.run_log import final_status, record_run
from src.run_status import RunStatus

T0 = datetime(2026, 9, 19, 10, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 19, 10, 1, 30, tzinfo=timezone.utc)


def _status() -> RunStatus:
    s = RunStatus(articles_collected=40, articles_after_dedup=31,
                  batches_total=4, batches_failed=1)
    s.record_usage(1200, 300, 0.0009)
    s.add("Análise: 1 de 4 lotes falharam (1 artigos não analisados)")
    return s


def _rows(db):
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM runs ORDER BY id")]


def test_record_run_creates_table_and_inserts_row(tmp_path):
    db = tmp_path / "nested" / "runs.db"
    assert record_run(db, T0, T1, "partial", _status(), model="gpt-4o-mini") is True

    [row] = _rows(db)
    assert row["started_at"] == "2026-09-19T10:00:00+00:00"
    assert row["finished_at"] == "2026-09-19T10:01:30+00:00"
    assert row["status"] == "partial"
    assert (row["articles_collected"], row["articles_after_dedup"]) == (40, 31)
    assert (row["batches_total"], row["batches_failed"]) == (4, 1)
    assert (row["prompt_tokens"], row["completion_tokens"]) == (1200, 300)
    assert row["cost_usd"] == pytest.approx(0.0009)
    assert row["model"] == "gpt-4o-mini"
    assert json.loads(row["warnings"]) == ["Análise: 1 de 4 lotes falharam (1 artigos não analisados)"]
    assert row["error"] is None


def test_record_run_appends_across_runs(tmp_path):
    db = tmp_path / "runs.db"
    record_run(db, T0, T1, "success", RunStatus())
    record_run(db, T0, T1, "failed", RunStatus(), error="boom")
    assert [r["status"] for r in _rows(db)] == ["success", "failed"]


def test_unknown_cost_is_stored_as_null(tmp_path):
    db = tmp_path / "runs.db"
    s = RunStatus()
    s.record_usage(10, 5, None)
    record_run(db, T0, T1, "success", s)
    assert _rows(db)[0]["cost_usd"] is None


def test_check_constraint_rejects_invalid_status(tmp_path):
    db = tmp_path / "runs.db"
    assert record_run(db, T0, T1, "exploded", RunStatus()) is False
    assert _rows(db) == []


def test_record_run_never_raises_on_unwritable_path(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("not a dir")
    assert record_run(blocker / "runs.db", T0, T1, "success", RunStatus()) is False


def test_queries_file_runs_against_schema(tmp_path):
    """sql/queries.sql tem que ser SQL válido para o schema atual."""
    from pathlib import Path
    db = tmp_path / "runs.db"
    record_run(db, T0, T1, "partial", _status())
    queries = (Path(__file__).resolve().parent.parent / "sql" / "queries.sql").read_text()
    sql = "\n".join(l for l in queries.splitlines() if not l.startswith("."))  # remove comandos do CLI sqlite3
    with sqlite3.connect(db) as conn:
        for stmt in filter(str.strip, sql.split(";")):
            conn.execute(stmt).fetchall()


@pytest.mark.parametrize("crashed,delivered,warnings,failed,expected", [
    (False, True, [], 0, "success"),
    (False, True, ["x"], 0, "partial"),
    (False, True, [], 1, "partial"),
    (False, False, [], 0, "failed"),
    (True, False, [], 0, "failed"),
])
def test_final_status(crashed, delivered, warnings, failed, expected):
    s = RunStatus(warnings=list(warnings), batches_failed=failed)
    assert final_status(s, crashed=crashed, delivered=delivered) == expected
