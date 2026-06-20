import base64
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.models import Article

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _build_service():
    token_json = os.getenv("GMAIL_TOKEN_JSON")
    if token_json:
        token_data = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    else:
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            with open("token.json", "w") as f:
                f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def extract_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)

    parts = payload.get("parts", [])
    plain = next((p for p in parts if p.get("mimeType") == "text/plain"), None)
    if plain:
        return extract_body(plain)
    html_part = next((p for p in parts if p.get("mimeType") == "text/html"), None)
    if html_part:
        return extract_body(html_part)
    for part in parts:
        result = extract_body(part)
        if result:
            return result
    return ""


def _get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def read_gmail(label: str = "newsletters") -> list[Article]:
    try:
        service = _build_service()
    except Exception as e:
        logger.error("Failed to build Gmail service: %s", e)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    try:
        labels_response = service.users().labels().list(userId="me").execute()
        label_id = next(
            (l["id"] for l in labels_response.get("labels", []) if l["name"] == label),
            None,
        )
        if not label_id:
            logger.warning("Gmail label '%s' not found", label)
            return []

        messages_response = (
            service.users()
            .messages()
            .list(userId="me", labelIds=[label_id], maxResults=50)
            .execute()
        )
        messages = messages_response.get("messages", [])
    except Exception as e:
        logger.error("Failed to list Gmail messages: %s", e)
        return []

    articles: list[Article] = []
    for msg in messages:
        try:
            full = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()
            payload = full["payload"]
            headers = payload.get("headers", [])

            date_str = _get_header(headers, "Date")
            try:
                published_at = parsedate_to_datetime(date_str).astimezone(timezone.utc)
            except Exception:
                continue

            if published_at < cutoff:
                continue

            subject = _get_header(headers, "Subject") or "(sem assunto)"
            sender = _get_header(headers, "From")
            body = extract_body(payload)

            articles.append(
                Article(
                    source=sender,
                    title=subject,
                    content=body[:5000],
                    url="",
                    published_at=published_at,
                )
            )
        except Exception as e:
            logger.error("Failed to process message %s: %s", msg["id"], e)

    return articles
