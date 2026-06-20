import base64
import json
from unittest.mock import patch, MagicMock
from src.gmail_reader import extract_body, read_gmail
from src.models import Article


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_extract_body_prefers_plain_text():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64("Plain text content")}},
            {"mimeType": "text/html", "body": {"data": _b64("<p>HTML content</p>")}},
        ],
    }
    assert extract_body(payload) == "Plain text content"


def test_extract_body_falls_back_to_html():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "text/html", "body": {"data": _b64("<p>HTML only</p>")}},
        ],
    }
    result = extract_body(payload)
    assert "HTML only" in result


def test_extract_body_simple_plain():
    payload = {
        "mimeType": "text/plain",
        "body": {"data": _b64("Simple plain text")},
    }
    assert extract_body(payload) == "Simple plain text"


def test_read_gmail_returns_articles():
    mock_service = MagicMock()

    mock_service.users().labels().list().execute.return_value = {
        "labels": [{"id": "Label_123", "name": "newsletters"}]
    }
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg1"}]
    }
    mock_service.users().messages().get().execute.return_value = {
        "id": "msg1",
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": _b64("Newsletter content")},
            "headers": [
                {"name": "Subject", "value": "Weekly Newsletter"},
                {"name": "From", "value": "editor@example.com"},
                {"name": "Date", "value": "Fri, 20 Jun 2026 08:00:00 +0000"},
            ],
        },
    }

    with patch("src.gmail_reader._build_service", return_value=mock_service):
        articles = read_gmail("newsletters")

    assert len(articles) == 1
    assert articles[0].title == "Weekly Newsletter"
    assert articles[0].source == "editor@example.com"
    assert "Newsletter content" in articles[0].content
    assert isinstance(articles[0], Article)
