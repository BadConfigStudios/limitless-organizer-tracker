import hmac

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel

import app.config
from app.api.auth import (
    SESSION_MAX_AGE_SECONDS,
    create_session_token,
    require_api_key,
    verify_session_token,
    session_gate_configured,
)

router = APIRouter(prefix="/api/auth", tags=["auth"], dependencies=[Depends(require_api_key)])


class LoginIn(BaseModel):
    username: str
    password: str


class SessionOut(BaseModel):
    authenticated: bool


def _credentials_valid(username: str, password: str) -> bool:
    settings = app.config.settings
    if not settings.admin_username or not settings.admin_password:
        return False
    return hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(
        password, settings.admin_password
    )


@router.post("/login", response_model=SessionOut)
def login(body: LoginIn, response: Response) -> SessionOut:
    if not _credentials_valid(body.username, body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_session_token()
    response.set_cookie(
        "session_token",
        token,
        httponly=True,
        samesite="lax",
        secure=app.config.settings.session_cookie_secure,
        max_age=SESSION_MAX_AGE_SECONDS,
    )
    return SessionOut(authenticated=True)


@router.post("/logout", response_model=SessionOut)
def logout(response: Response) -> SessionOut:
    response.delete_cookie("session_token")
    return SessionOut(authenticated=False)


@router.get("/session", response_model=SessionOut)
def get_session(session_token: str | None = Cookie(None)) -> SessionOut:
    if not session_gate_configured():
        return SessionOut(authenticated=True)
    authenticated = session_token is not None and verify_session_token(session_token)
    return SessionOut(authenticated=authenticated)
