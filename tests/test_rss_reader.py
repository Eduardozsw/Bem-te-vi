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


def test_bad_entry_does_not_kill_remaining_entries(tmp_path):
    """A malformed entry should be skipped without dropping subsequent good entries."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("rss_feeds:\n  - name: Test\n    url: http://example.com/rss\n")

    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=6)).timetuple()

    # A bad entry whose published_parsed is valid but that raises when processed further.
    # We simulate this by giving it a bad published_parsed that causes timegm to raise.
    class BadEntry:
        def get(self, key, default=None):
            if key == "published_parsed":
                return recent
            return default

        @property
        def published_parsed(self):
            raise OverflowError("simulated overflow")

        @property
        def title(self):
            return "bad"

        @property
        def link(self):
            return "http://example.com/bad"

        @property
        def summary(self):
            return "bad"

    good_entry = MagicMock()
    good_entry.get.return_value = recent
    good_entry.published_parsed = recent
    good_entry.title = "Good article"
    good_entry.link = "http://example.com/good"
    good_entry.summary = "Good content"

    mock_feed = MagicMock()
    mock_feed.entries = [BadEntry(), good_entry]

    with patch("feedparser.parse", return_value=mock_feed):
        articles = read_rss_feeds(str(config_file))

    assert len(articles) == 1
    assert articles[0].title == "Good article"


def test_read_rss_warns_when_feed_down(tmp_path):
    from src.run_status import RunStatus
    config_file = tmp_path / "config.yaml"
    config_file.write_text("rss_feeds:\n  - name: TechCrunch\n    url: http://x/rss\n")
    status = RunStatus()
    with patch("feedparser.parse", side_effect=Exception("network error")):
        articles = read_rss_feeds(str(config_file), status=status)
    assert articles == []
    assert any("TechCrunch" in w for w in status.warnings)
