import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from src.run_status import RunStatus

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"

INSERT_RUN = """
INSERT INTO runs (
    started_at, finished_at, status,
    articles_collected, articles_after_dedup,
    batches_total, batches_failed,
    prompt_tokens, completion_tokens, cost_usd,
    model, warnings, error
) VALUES (
    :started_at, :finished_at, :status,
    :articles_collected, :articles_after_dedup,
    :batches_total, :batches_failed,
    :prompt_tokens, :completion_tokens, :cost_usd,
    :model, :warnings, :error
)
"""


def final_status(status: RunStatus, crashed: bool, delivered: bool) -> str:
    if crashed or not delivered:
        return "failed"
    if status.warnings or status.batches_failed:
        return "partial"
    return "success"


def record_run(
    db_path: str | Path,
    started_at: datetime,
    finished_at: datetime,
    run_status: str,
    status: RunStatus,
    model: str | None = None,
    error: str | None = None,
) -> bool:
    """Grava uma linha em `runs`. Nunca levanta exceção: o registro não pode derrubar o pipeline."""
    try:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            conn.execute(
                INSERT_RUN,
                {
                    "started_at": started_at.isoformat(timespec="seconds"),
                    "finished_at": finished_at.isoformat(timespec="seconds"),
                    "status": run_status,
                    "articles_collected": status.articles_collected,
                    "articles_after_dedup": status.articles_after_dedup,
                    "batches_total": status.batches_total,
                    "batches_failed": status.batches_failed,
                    "prompt_tokens": status.prompt_tokens,
                    "completion_tokens": status.completion_tokens,
                    "cost_usd": status.total_cost_usd,
                    "model": model,
                    "warnings": json.dumps(status.warnings, ensure_ascii=False),
                    "error": error,
                },
            )
        conn.close()
        return True
    except Exception:
        logger.exception("Could not record run in %s", db_path)
        return False
