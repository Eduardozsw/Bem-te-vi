from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from src.rss_reader import read_rss_feeds
from src.models import Article


def _make_entry(title, url, published_parsed):
    entry = MagicMock()
    entry.title = title
    entry.link = url
    entry.summary = "Entry summary content"
    entry.published_parsed = published_parsed
    return entry


def test_returns_articles_within_24h(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("rss_feeds:\n  - name: Test\n    url: http://example.com/rss\n")

    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=12)).timetuple()
    old = (now - timedelta(hours=25)).timetuple()

    mock_feed = MagicMock()
    mock_feed.entries = [
        _make_entry("Recent article", "http://example.com/1", recent),
        _make_entry("Old article", "http://example.com/2", old),
    ]

    with patch("feedparser.parse", return_value=mock_feed):
        articles = read_rss_feeds(str(config_file))

    assert len(articles) == 1
    assert articles[0].title == "Recent article"
    assert articles[0].source == "Test"
    assert isinstance(articles[0], Article)


def test_returns_empty_when_no_recent_entries(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("rss_feeds:\n  - name: Test\n    url: http://example.com/rss\n")

    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=30)).timetuple()

    mock_feed = MagicMock()
    mock_feed.entries = [_make_entry("Old article", "http://example.com/1", old)]

    with patch("feedparser.parse", return_value=mock_feed):
        articles = read_rss_feeds(str(config_file))

    assert articles == []


def test_returns_empty_on_missing_config(tmp_path):
    articles = read_rss_feeds(str(tmp_path / "nonexistent.yaml"))
    assert articles == []
