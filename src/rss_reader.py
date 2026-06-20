import calendar
import logging
from datetime import datetime, timezone, timedelta

import feedparser
import yaml

from src.models import Article

logger = logging.getLogger(__name__)


def read_rss_feeds(config_path: str = "config.yaml") -> list[Article]:
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning("config.yaml not found at %s", config_path)
        return []

    feeds = config.get("rss_feeds", [])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    articles: list[Article] = []

    for feed_cfg in feeds:
        try:
            name = feed_cfg["name"]
            url = feed_cfg["url"]
        except KeyError as e:
            logger.warning("Skipping malformed feed config entry (missing key: %s)", e)
            continue
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if not entry.get("published_parsed"):
                    continue
                published_at = datetime.fromtimestamp(
                    calendar.timegm(entry.published_parsed), tz=timezone.utc
                )
                if published_at < cutoff:
                    continue
                content = getattr(entry, "summary", "") or ""
                articles.append(
                    Article(
                        source=name,
                        title=entry.title,
                        content=content,
                        url=entry.link,
                        published_at=published_at,
                    )
                )
        except Exception as e:
            logger.error("Failed to fetch feed %s: %s", url, e)

    return articles
