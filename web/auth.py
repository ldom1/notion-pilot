"""JWT auth utilities for the Notion Pilot web server."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

# Use pbkdf2_sha256 for testing compatibility; bcrypt can be expensive in test environments
_PWD_CONTEXT = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _PWD_CONTEXT.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _PWD_CONTEXT.verify(plain, hashed)


def create_access_token(data: dict, *, secret_key: str, expire_minutes: int) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(tz=timezone.utc) + timedelta(minutes=expire_minutes)
    return jwt.encode(payload, secret_key, algorithm=_ALGORITHM)


def verify_token(token: str, *, secret_key: str) -> dict:
    """Decode and verify a JWT. Raises JWTError on failure."""
    return jwt.decode(token, secret_key, algorithms=[_ALGORITHM])
