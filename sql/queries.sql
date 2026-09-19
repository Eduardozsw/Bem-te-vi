-- Métricas operacionais do Bem-te-vi.
-- Uso: sqlite3 runs.db < sql/queries.sql
.headers on
.mode column

-- 1. Visão geral: N de execuções e distribuição por status
SELECT
    COUNT(*)                                                    AS n_runs,
    SUM(status = 'success')                                     AS success,
    SUM(status = 'partial')                                     AS partial,
    SUM(status = 'failed')                                      AS failed,
    ROUND(100.0 * SUM(status = 'success') / COUNT(*), 1)        AS success_pct,
    MIN(started_at)                                             AS first_run,
    MAX(started_at)                                             AS last_run
FROM runs;

-- 2. Confiabilidade da análise: lotes com falha sobre o total de lotes
SELECT
    SUM(batches_total)                                          AS batches_total,
    SUM(batches_failed)                                         AS batches_failed,
    ROUND(100.0 * SUM(batches_failed) / NULLIF(SUM(batches_total), 0), 2)
                                                                AS batches_failed_pct
FROM runs;

-- 3. Volume: artigos coletados vs. após deduplicação (só execuções que coletaram algo)
SELECT
    COUNT(*)                                                    AS n_runs,
    ROUND(AVG(articles_collected), 1)                           AS avg_collected,
    ROUND(AVG(articles_after_dedup), 1)                         AS avg_after_dedup,
    ROUND(100.0 * (1 - 1.0 * SUM(articles_after_dedup) / SUM(articles_collected)), 1)
                                                                AS dedup_reduction_pct
FROM runs
WHERE articles_collected > 0;

-- 4. Custo e tokens. Execuções com cost_usd NULL ficam fora das somas e são contadas à parte.
SELECT
    COUNT(cost_usd)                                             AS runs_priced,
    SUM(cost_usd IS NULL)                                       AS runs_unpriced,
    ROUND(SUM(cost_usd), 4)                                     AS total_cost_usd,
    ROUND(AVG(cost_usd), 5)                                     AS avg_cost_usd,
    ROUND(AVG(prompt_tokens + completion_tokens))               AS avg_tokens
FROM runs;

-- 5. Duração média (segundos) por status
SELECT
    status,
    COUNT(*)                                                    AS n_runs,
    ROUND(AVG((julianday(finished_at) - julianday(started_at)) * 86400), 1)
                                                                AS avg_duration_s
FROM runs
WHERE finished_at IS NOT NULL
GROUP BY status;

-- 6. Últimas 10 execuções
SELECT id, started_at, status, articles_collected, articles_after_dedup,
       batches_failed || '/' || batches_total AS failed_batches,
       ROUND(cost_usd, 6) AS cost_usd, error
FROM runs
ORDER BY started_at DESC
LIMIT 10;
