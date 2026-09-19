-- Registro de execuções do pipeline. Uma linha por execução de main.py.
-- Datas em ISO 8601 UTC (TEXT), como recomendado para SQLite.
CREATE TABLE IF NOT EXISTS runs (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at           TEXT    NOT NULL,
    finished_at          TEXT,
    status               TEXT    NOT NULL
                         CHECK (status IN ('success', 'partial', 'failed')),
    articles_collected   INTEGER NOT NULL DEFAULT 0 CHECK (articles_collected >= 0),
    articles_after_dedup INTEGER NOT NULL DEFAULT 0 CHECK (articles_after_dedup >= 0),
    batches_total        INTEGER NOT NULL DEFAULT 0 CHECK (batches_total >= 0),
    batches_failed       INTEGER NOT NULL DEFAULT 0
                         CHECK (batches_failed BETWEEN 0 AND batches_total),
    prompt_tokens        INTEGER NOT NULL DEFAULT 0,
    completion_tokens    INTEGER NOT NULL DEFAULT 0,
    cost_usd             REAL,          -- NULL = alguma chamada sem preço conhecido
    model                TEXT,
    warnings             TEXT NOT NULL DEFAULT '[]',  -- array JSON de strings
    error                TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs (started_at);
