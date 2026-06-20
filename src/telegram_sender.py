import html
import logging
import os
from datetime import datetime, timezone

import requests

from src.models import AnalysisResult

logger = logging.getLogger(__name__)

SEPARATOR = "━" * 22
TELEGRAM_LIMIT = 4096


def format_report(results: list[AnalysisResult], total_analyzed: int) -> str:
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    important = [r for r in results if r.relevance >= 6]
    ignored = [r for r in results if r.relevance <= 5]

    lines = [
        f"📊 <b>Inteligência Diária — {today}</b>\n",
        f"Analisados: {total_analyzed} conteúdos | Importantes: {len(important)} | Ignorados: {len(ignored)}",
    ]

    for result in sorted(important, key=lambda r: r.relevance, reverse=True):
        emoji = "🔴" if result.relevance >= 8 else "🟡"
        block = [
            f"\n{SEPARATOR}",
            f"{emoji} <b>[{result.relevance}/10] {html.escape(result.title)}</b>",
            f"📌 Fonte: {html.escape(result.source)}",
            f"\n{html.escape(result.summary)}",
            f"\nPor que importa: {html.escape(result.why_it_matters)}",
        ]
        if result.impacts:
            block.append("\nImpactos:")
            block.extend(f"• {html.escape(impact)}" for impact in result.impacts)
        if result.actions:
            block.append("\nAções possíveis:")
            block.extend(f"• {html.escape(action)}" for action in result.actions)
        lines.extend(block)

    if ignored:
        lines.append(f"\n{SEPARATOR}")
        lines.append(f"⚪ <b>Ignorados ({len(ignored)})</b>\n")
        for result in ignored:
            lines.append(f"• {html.escape(result.summary or result.title)} — {html.escape(result.source)}")

    return "\n".join(lines)


def split_messages(text: str) -> list[str]:
    if len(text) <= TELEGRAM_LIMIT:
        return [text]

    parts = []
    current = ""
    for block in text.split(SEPARATOR):
        chunk = (SEPARATOR + block) if current else block
        if len(current) + len(chunk) > TELEGRAM_LIMIT:
            if current:
                parts.append(current.strip())
            current = chunk
        else:
            current += chunk
    if current.strip():
        parts.append(current.strip())
    return parts


def send_report(results: list[AnalysisResult], total_analyzed: int) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return

    report = format_report(results, total_analyzed)
    messages = split_messages(report)
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for message in messages:
        try:
            response = requests.post(
                url,
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10,
            )
            if not response.ok:
                logger.error("Telegram API error: %s", response.text)
        except Exception as e:
            logger.error("Failed to send Telegram message: %s", e)
