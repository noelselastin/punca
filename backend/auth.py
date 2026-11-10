"""Local email + password accounts for the MVP (student and lecturer roles).

Passwords are stored only as salted PBKDF2-SHA256 hashes. Session tokens are random and stored only as
SHA-256 digests. Firebase Authentication can replace this module later: keep the same role field on users.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

ITERATIONS = 200_000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TOKEN_TTL_DAYS = 7


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iters))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email)) and len(email) <= 120


PERSONAL_GMAIL_DOMAINS = ("gmail.com", "googlemail.com")


def is_personal_gmail(email: str) -> bool:
    """Sign-up asks for a personal Gmail address: it is the Google account Punca connects to."""
    return valid_email(email) and email.rsplit("@", 1)[-1].lower() in PERSONAL_GMAIL_DOMAINS
