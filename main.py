import logging
import os
import sys

from dotenv import load_dotenv

from src.analyzer import analyze
from src.deduplicator import deduplicate
from src.gmail_reader import read_gmail
from src.profile import load_profile
from src.rss_reader import read_rss_feeds
from src.run_status import RunStatus
from src.telegram_sender import send_alert, send_report

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    status = RunStatus()
    try:
        label = os.getenv("GMAIL_LABEL", "newsletters")

        logger.info("Fetching Gmail newsletters (label: %s)...", label)
        gmail_articles = read_gmail(label, status=status)
        logger.info("Found %d Gmail articles", len(gmail_articles))

        logger.info("Fetching RSS feeds...")
        rss_articles = read_rss_feeds("config.yaml", status=status)
        logger.info("Found %d RSS articles", len(rss_articles))

        all_articles = gmail_articles + rss_articles
        if not all_articles:
            status.add("Nenhum conteúdo encontrado nas últimas 24h")

        logger.info("Deduplicating %d articles...", len(all_articles))
        deduped = deduplicate(all_articles, status=status)
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
            logger.error("Report delivery failed")
            sys.exit(1)

        logger.info("Done.")
    except Exception as e:
        logger.exception("Pipeline crashed")
        send_alert(f"\U0001f6a8 Pipeline falhou: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
