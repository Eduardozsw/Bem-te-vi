import logging
import os

from dotenv import load_dotenv

from src.analyzer import analyze
from src.gmail_reader import read_gmail
from src.rss_reader import read_rss_feeds
from src.telegram_sender import send_report

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    label = os.getenv("GMAIL_LABEL", "newsletters")

    logger.info("Fetching Gmail newsletters (label: %s)...", label)
    gmail_articles = read_gmail(label)
    logger.info("Found %d Gmail articles", len(gmail_articles))

    logger.info("Fetching RSS feeds...")
    rss_articles = read_rss_feeds("config.yaml")
    logger.info("Found %d RSS articles", len(rss_articles))

    all_articles = gmail_articles + rss_articles
    logger.info("Total articles to analyze: %d", len(all_articles))

    results = analyze(all_articles)
    logger.info("Analysis complete. Sending report...")

    send_report(results, total_analyzed=len(all_articles))
    logger.info("Done.")


if __name__ == "__main__":
    main()
