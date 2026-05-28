# tests/unit/web/test_auth.py
import pytest
from web.auth import create_access_token, hash_password, verify_password, verify_token


def test_hash_and_verify_password():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_create_and_verify_token():
    token = create_access_token({"sub": "admin"}, secret_key="testsecret", expire_minutes=60)
    payload = verify_token(token, secret_key="testsecret")
    assert payload["sub"] == "admin"


def test_verify_token_expired():
    token = create_access_token({"sub": "admin"}, secret_key="testsecret", expire_minutes=-1)
    with pytest.raises(Exception):
        verify_token(token, secret_key="testsecret")


def test_verify_token_wrong_key():
    token = create_access_token({"sub": "admin"}, secret_key="testsecret", expire_minutes=60)
    with pytest.raises(Exception):
        verify_token(token, secret_key="wrongkey")
