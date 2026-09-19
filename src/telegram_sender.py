import html
import logging
import os
from datetime import datetime, timezone

import requests

from src.models import AnalysisResult

logger = logging.getLogger(__name__)

SEPARATOR = "━" * 22
TELEGRAM_LIMIT = 4096


DEFAULT_MIN_RELEVANCE = 7
DEFAULT_MAX_HIGHLIGHTS = 5
MAX_ALSO_RELEVANT = 10


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        logger.warning("Invalid %s, using default %d", name, default)
        return default


def _linked_title(result: AnalysisResult) -> str:
    title = html.escape(result.title)
    if not result.url:
        return title
    return f'<a href="{html.escape(result.url, quote=True)}">{title}</a>'


def _highlight_block(result: AnalysisResult) -> list[str]:
    emoji = "🔴" if result.relevance >= 8 else "🟡"
    block = [
        f"\n{SEPARATOR}",
        f"{emoji} <b>[{result.relevance}/10] {_linked_title(result)}</b>",
    ]
    if result.affects:
        block.append(
            "🏷️ Afeta: " + ", ".join(html.escape(a) for a in result.affects)
        )
    block.extend([
        (
            f"📌 Visto em: {', '.join(html.escape(s) for s in result.sources)}"
            if len(result.sources) > 1
            else f"📌 Fonte: {html.escape(result.source)}"
        ),
        f"\n{html.escape(result.summary)}",
        f"\nPor que importa: {html.escape(result.why_it_matters)}",
    ])
    if result.impacts:
        block.append("\nImpactos:")
        block.extend(f"• {html.escape(impact)}" for impact in result.impacts)
    if result.actions:
        block.append("\nAções possíveis:")
        block.extend(f"• {html.escape(action)}" for action in result.actions)
    return block


def format_report(results: list[AnalysisResult], total_analyzed: int, warnings: list[str] | None = None) -> str:
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    min_relevance = _env_int("REPORT_MIN_RELEVANCE", DEFAULT_MIN_RELEVANCE)
    max_highlights = _env_int("REPORT_MAX_HIGHLIGHTS", DEFAULT_MAX_HIGHLIGHTS)

    relevant = sorted(
        (r for r in results if r.relevance >= min_relevance),
        key=lambda r: r.relevance,
        reverse=True,
    )
    highlights = relevant[:max_highlights]
    also_relevant = relevant[max_highlights:]
    below_cut = len(results) - len(relevant)

    lines = [
        f"📊 <b>Inteligência Diária — {today}</b>\n",
        f"Analisados: {total_analyzed} conteúdos | Destaques: {len(highlights)} | "
        f"Abaixo de {min_relevance}/10: {below_cut}",
    ]

    if not relevant:
        lines.append(f"\nNada acima de {min_relevance}/10 hoje. 🌤️")

    for result in highlights:
        lines.extend(_highlight_block(result))

    if also_relevant:
        lines.append(f"\n{SEPARATOR}")
        lines.append(f"➕ <b>Também relevantes ({len(also_relevant)})</b>\n")
        for result in also_relevant[:MAX_ALSO_RELEVANT]:
            lines.append(f"• [{result.relevance}/10] {_linked_title(result)}")
        hidden = len(also_relevant) - MAX_ALSO_RELEVANT
        if hidden > 0:
            lines.append(f"• … e mais {hidden}")

    if warnings:
        lines.append(f"\n{SEPARATOR}")
        lines.append("⚠️ <b>Avisos</b>\n")
        for w in warnings:
            lines.append(f"• {html.escape(w)}")

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


def _post_message(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "link_preview_options": {"is_disabled": True},
            },
            timeout=10,
        )
        if not response.ok:
            logger.error("Telegram API error: %s", response.text)
            return False
        return True
    except Exception as e:
        logger.error("Failed to send Telegram message: %s", e)
        return False


def send_report(results: list[AnalysisResult], total_analyzed: int, warnings: list[str] | None = None) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False

    report = format_report(results, total_analyzed, warnings)
    messages = split_messages(report)

    all_ok = True
    for message in messages:
        if not _post_message(token, chat_id, message):
            all_ok = False
    return all_ok


def send_alert(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set; cannot send alert")
        return False
    return _post_message(token, chat_id, html.escape(text))
