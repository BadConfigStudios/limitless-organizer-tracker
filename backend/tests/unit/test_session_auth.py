from app.api.auth import create_session_token, verify_session_token
import app.config


def _with_secret(monkeypatch, secret="test-secret-key"):
    monkeypatch.setattr(app.config.settings, "session_secret_key", secret)


def test_create_and_verify_round_trip(monkeypatch):
    _with_secret(monkeypatch)
    token = create_session_token()
    assert verify_session_token(token) is True


def test_verify_rejects_tampered_signature(monkeypatch):
    _with_secret(monkeypatch)
    token = create_session_token()
    payload, _sig = token.split(".", 1)
    tampered = f"{payload}.deadbeef"
    assert verify_session_token(tampered) is False


def test_verify_rejects_malformed_token(monkeypatch):
    _with_secret(monkeypatch)
    assert verify_session_token("not-a-valid-token") is False


def test_verify_rejects_expired_token(monkeypatch):
    _with_secret(monkeypatch)
    monkeypatch.setattr("app.api.auth.SESSION_MAX_AGE_SECONDS", -1)
    token = create_session_token()
    assert verify_session_token(token) is False


def test_verify_rejects_token_signed_with_different_secret(monkeypatch):
    _with_secret(monkeypatch, secret="secret-a")
    token = create_session_token()
    _with_secret(monkeypatch, secret="secret-b")
    assert verify_session_token(token) is False
