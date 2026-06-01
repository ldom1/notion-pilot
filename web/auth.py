"""JWT auth utilities for the Notion Pilot web server."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, *, secret_key: str, expire_minutes: int) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(tz=timezone.utc) + timedelta(minutes=expire_minutes)
    return jwt.encode(payload, secret_key, algorithm=_ALGORITHM)


def verify_token(token: str, *, secret_key: str) -> dict:
    """Decode and verify a JWT. Raises JWTError on failure."""
    return jwt.decode(token, secret_key, algorithms=[_ALGORITHM])
