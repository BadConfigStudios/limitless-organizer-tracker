import hashlib
import hmac
import time

from fastapi import Cookie, HTTPException, Security
from fastapi.security import APIKeyHeader

import app.config

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

SESSION_MAX_AGE_SECONDS = 12 * 60 * 60  # 12 hours


def _parse_keys() -> set[str]:
    return {k.strip() for k in app.config.settings.api_keys.split(",") if k.strip()}


async def require_api_key(key: str | None = Security(_api_key_header)) -> str | None:
    valid_keys = _parse_keys()
    if not valid_keys:
        return None
    if key is None or key not in valid_keys:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return key


def session_gate_configured() -> bool:
    settings = app.config.settings
    return bool(settings.admin_username and settings.admin_password and settings.session_secret_key)


def create_session_token() -> str:
    expiry = int(time.time()) + SESSION_MAX_AGE_SECONDS
    payload = str(expiry)
    signature = hmac.new(
        app.config.settings.session_secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_session_token(token: str) -> bool:
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return False
    expected = hmac.new(
        app.config.settings.session_secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        expiry = int(payload)
    except ValueError:
        return False
    return time.time() < expiry


async def require_session(session_token: str | None = Cookie(None)) -> None:
    if not session_gate_configured():
        return None
    if session_token is None or not verify_session_token(session_token):
        raise HTTPException(status_code=401, detail="Login required")
