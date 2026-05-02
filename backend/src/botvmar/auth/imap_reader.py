"""IMAP email reader — polls inbox for OTP codes and magic links.

Uses Python stdlib only (imaplib + email). Synchronous — callers should
wrap calls with ``asyncio.to_thread()`` when used from async code.
"""

from __future__ import annotations

import email
import email.utils
import imaplib
import re
import time
from dataclasses import dataclass
from email.header import decode_header

from botvmar.utils.logger import get_logger

logger = get_logger("auth.imap")


@dataclass
class ImapConfig:
    """IMAP connection parameters (stored in bot_settings.imap_config)."""

    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> ImapConfig:
        return cls(
            host=d["host"],
            port=int(d.get("port", 993)),
            username=d["username"],
            password=d["password"],
            use_ssl=d.get("use_ssl", True),
        )


def _connect(cfg: ImapConfig) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
    if cfg.use_ssl:
        conn = imaplib.IMAP4_SSL(cfg.host, cfg.port)
    else:
        conn = imaplib.IMAP4(cfg.host, cfg.port)
    conn.login(cfg.username, cfg.password)
    conn.select("INBOX")
    return conn


def _decode_subject(msg: email.message.Message) -> str:
    raw = msg.get("Subject", "")
    parts = decode_header(raw)
    fragments: list[str] = []
    for part, charset in parts:
        if isinstance(part, bytes):
            fragments.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            fragments.append(str(part))
    return " ".join(fragments)


def get_body(msg: email.message.Message) -> str:
    """Extract the text (plain or HTML) body from an email message."""
    if msg.is_multipart():
        plain = ""
        html = ""
        for part in msg.walk():
            ct = part.get_content_type()
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            text = payload.decode("utf-8", errors="replace")
            if ct == "text/plain" and not plain:
                plain = text
            elif ct == "text/html" and not html:
                html = text
        # Prefer plain text, fall back to HTML
        return plain or html
    payload = msg.get_payload(decode=True)
    return payload.decode("utf-8", errors="replace") if payload else ""


def poll_for_email(
    cfg: ImapConfig,
    *,
    sender_filter: str,
    subject_contains: str | None = None,
    since_timestamp: float | None = None,
    timeout_seconds: int = 120,
    poll_interval: int = 5,
) -> email.message.Message | None:
    """Poll IMAP for a matching email. Returns the Message or None on timeout.

    Parameters
    ----------
    sender_filter : str
        Substring that must appear in the From address (e.g. ``"yahoo"``).
    subject_contains : str | None
        Optional substring filter on the Subject header.
    since_timestamp : float | None
        Ignore emails older than this Unix timestamp.
    timeout_seconds : int
        How long to poll before giving up.
    poll_interval : int
        Seconds between each IMAP check.
    """
    deadline = time.time() + timeout_seconds
    if since_timestamp is None:
        since_timestamp = time.time() - 30  # small look-back window

    while time.time() < deadline:
        conn: imaplib.IMAP4_SSL | imaplib.IMAP4 | None = None
        try:
            conn = _connect(cfg)
            # Search for emails from the sender
            _, msg_ids = conn.search(None, f'(FROM "{sender_filter}")')
            ids = msg_ids[0].split()

            # Check most recent first (last 30 messages max)
            for mid in reversed(ids[-30:]):
                _, data = conn.fetch(mid, "(RFC822)")
                raw = data[0][1]  # type: ignore[index]
                msg = email.message_from_bytes(raw)  # type: ignore[arg-type]

                # Subject filter
                if subject_contains:
                    subj = _decode_subject(msg)
                    if subject_contains.lower() not in subj.lower():
                        continue

                # Date filter — skip old emails
                date_str = msg.get("Date", "")
                date_tuple = email.utils.parsedate_tz(date_str)
                if date_tuple:
                    email_ts = email.utils.mktime_tz(date_tuple)
                    if email_ts < since_timestamp:
                        continue

                logger.info(
                    "Found matching email from=%s subject=%s",
                    msg.get("From", "?")[:60],
                    _decode_subject(msg)[:80],
                )
                return msg

        except Exception as e:
            logger.warning("IMAP poll error: %s", e)
        finally:
            if conn is not None:
                try:
                    conn.logout()
                except Exception:
                    pass

        time.sleep(poll_interval)

    logger.error("IMAP poll timed out after %ds (sender=%s)", timeout_seconds, sender_filter)
    return None


def extract_otp(body: str, pattern: str = r"\b(\d{6})\b") -> str | None:
    """Extract a 6-digit OTP code from email body text."""
    # Try to find a standalone 6-digit code (most common for verification)
    match = re.search(pattern, body)
    return match.group(1) if match else None


def extract_magic_link(body: str, domain: str = "reddit.com") -> str | None:
    """Extract a URL containing *domain* from email body (HTML or plain text)."""
    # Match URLs — handle both plain text and href="..." in HTML
    url_pattern = rf'https?://[^\s"<>\')]*{re.escape(domain)}[^\s"<>\')]*'
    match = re.search(url_pattern, body)
    return match.group(0) if match else None
