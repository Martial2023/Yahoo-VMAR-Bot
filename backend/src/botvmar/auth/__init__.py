"""Automated platform login — Playwright + IMAP email verification."""

from botvmar.auth.imap_reader import ImapConfig, extract_magic_link, extract_otp, poll_for_email
from botvmar.auth.login_reddit import auto_login_reddit
from botvmar.auth.login_stocktwits import auto_login_stocktwits
from botvmar.auth.login_yahoo import auto_login_yahoo

__all__ = [
    "ImapConfig",
    "auto_login_reddit",
    "auto_login_stocktwits",
    "auto_login_yahoo",
    "extract_magic_link",
    "extract_otp",
    "poll_for_email",
]
