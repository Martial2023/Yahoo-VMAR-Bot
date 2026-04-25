"""Notifications — Telegram (sync) and email via SMTP (async).

Email recipients come from runtime settings (`alert_emails`); SMTP credentials
come from .env. Telegram remains as an optional second channel.
"""

from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib
import requests

from botvmar.config import runtime
from botvmar.config.env import (
    SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
)
from botvmar.utils.logger import get_logger

logger = get_logger("notifier")

_LEVELS = {"info", "warning", "error", "critical"}


def _telegram(message: str, level: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": f"[{level.upper()}] VMAR Bot\n\n{message}",
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning("Telegram returned %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.error("Telegram send failed: %s", e)


async def _email(subject: str, body: str, recipients: list[str]) -> None:
    if not SMTP_HOST or not recipients or not SMTP_FROM:
        return
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER or None,
            password=SMTP_PASSWORD or None,
            start_tls=SMTP_PORT == 587,
            use_tls=SMTP_PORT == 465,
        )
        logger.debug("Email sent to %d recipient(s)", len(recipients))
    except Exception as e:
        logger.error("SMTP send failed: %s", e)


async def notify(message: str, level: str = "info") -> None:
    """Send a notification on every configured channel.

    Email is only sent for level in {"error", "critical"} to avoid spam.
    """
    if level not in _LEVELS:
        level = "info"

    log_fn = getattr(logger, "error" if level == "critical" else level, logger.info)
    log_fn("Notification: %s", message)

    _telegram(message, level)

    if level in ("error", "critical"):
        try:
            settings = await runtime.get()
            await _email(
                subject=f"[{level.upper()}] VMAR Bot",
                body=message,
                recipients=settings.alert_emails,
            )
        except Exception as e:
            logger.error("Email notification failed: %s", e)
