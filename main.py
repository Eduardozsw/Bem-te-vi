import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from src.analyzer import analyze
from src.deduplicator import deduplicate
from src.llm import current_model
from src.profile import load_profile
from src.rss_reader import read_rss_feeds
from src.run_log import final_status, record_run
from src.run_status import RunStatus
from src.telegram_sender import send_alert, send_report

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_RUNS_DB = "data/runs.db"


def main() -> None:
    status = RunStatus()
    started_at = datetime.now(timezone.utc)
    crashed = False
    delivered = False
    error: str | None = None
    try:
        logger.info("Fetching RSS feeds...")
        all_articles = read_rss_feeds("config.yaml", status=status)
        logger.info("Found %d RSS articles", len(all_articles))

        status.articles_collected = len(all_articles)
        if not all_articles:
            status.add("Nenhum conteúdo encontrado nas últimas 24h")

        logger.info("Deduplicating %d articles...", len(all_articles))
        deduped = deduplicate(all_articles, status=status)
        status.articles_after_dedup = len(deduped)
        logger.info("After dedup: %d distinct items", len(deduped))

        profile = load_profile()
        if profile:
            logger.info("Loaded user profile with %d top-level keys", len(profile))

        results = analyze(deduped, profile=profile, status=status)
        logger.info("Analysis complete. Sending report...")

        delivered = send_report(
            results, total_analyzed=len(deduped), warnings=status.warnings
        )
        if not delivered:
            error = "Report delivery failed"
            logger.error(error)
    except Exception as e:
        crashed = True
        error = f"{type(e).__name__}: {e}"
        logger.exception("Pipeline crashed")
        send_alert(f"\U0001f6a8 Pipeline falhou: {e}")
    finally:
        run_status = final_status(status, crashed=crashed, delivered=delivered)
        record_run(
            os.getenv("RUNS_DB", DEFAULT_RUNS_DB),
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            run_status=run_status,
            status=status,
            model=current_model(),
            error=error,
        )
        logger.info("Run recorded: status=%s", run_status)

    if crashed or not delivered:
        sys.exit(1)
    logger.info("Done.")


if __name__ == "__main__":
    main()
