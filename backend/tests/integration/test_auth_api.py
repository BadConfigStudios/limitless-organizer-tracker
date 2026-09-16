import os

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.config
from app.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session_factory = sessionmaker(bind=engine)

    def override_get_db():
        db = test_session_factory()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    # https base_url: the app sets the session cookie with Secure=True by default
    # (matches the real deployment, which sits behind an HTTPS/Cloudflare tunnel),
    # and httpx's cookie jar only re-sends Secure cookies over an https origin.
    return TestClient(fastapi_app, base_url="https://testserver")


class TestAuthConfigured:
    def setup_method(self):
        os.environ["ADMIN_USERNAME"] = "owner"
        os.environ["ADMIN_PASSWORD"] = "correct-horse"
        os.environ["SESSION_SECRET_KEY"] = "test-signing-key"
        app.config.settings = Settings()
        self.client = _make_client()

    def teardown_method(self):
        fastapi_app.dependency_overrides.clear()
        for k in ("ADMIN_USERNAME", "ADMIN_PASSWORD", "SESSION_SECRET_KEY"):
            os.environ.pop(k, None)
        app.config.settings = Settings()

    def test_admin_route_returns_401_without_session(self):
        resp = self.client.get("/api/admin/config")
        assert resp.status_code == 401

    def test_status_route_returns_401_without_session(self):
        resp = self.client.get("/api/status-history")
        assert resp.status_code == 401

    def test_organizers_route_does_not_require_session(self):
        resp = self.client.get("/api/games")
        assert resp.status_code == 200

    def test_login_with_wrong_credentials_returns_401(self):
        resp = self.client.post("/api/auth/login", json={"username": "owner", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_then_protected_route_succeeds(self):
        login_resp = self.client.post(
            "/api/auth/login", json={"username": "owner", "password": "correct-horse"}
        )
        assert login_resp.status_code == 200
        assert login_resp.json() == {"authenticated": True}

        resp = self.client.get("/api/admin/config")
        assert resp.status_code == 200

    def test_session_endpoint_reports_authenticated_after_login(self):
        self.client.post("/api/auth/login", json={"username": "owner", "password": "correct-horse"})
        resp = self.client.get("/api/auth/session")
        assert resp.json() == {"authenticated": True}

    def test_session_endpoint_reports_unauthenticated_before_login(self):
        resp = self.client.get("/api/auth/session")
        assert resp.json() == {"authenticated": False}

    def test_logout_clears_session(self):
        self.client.post("/api/auth/login", json={"username": "owner", "password": "correct-horse"})
        logout_resp = self.client.post("/api/auth/logout")
        assert logout_resp.status_code == 200

        resp = self.client.get("/api/admin/config")
        assert resp.status_code == 401


class TestAuthNotConfigured:
    def setup_method(self):
        for k in ("ADMIN_USERNAME", "ADMIN_PASSWORD", "SESSION_SECRET_KEY"):
            os.environ.pop(k, None)
        app.config.settings = Settings()
        self.client = _make_client()

    def teardown_method(self):
        fastapi_app.dependency_overrides.clear()
        app.config.settings = Settings()

    def test_admin_route_accessible_without_login_when_gate_disabled(self):
        resp = self.client.get("/api/admin/config")
        assert resp.status_code == 200

    def test_session_endpoint_reports_authenticated_when_gate_disabled(self):
        resp = self.client.get("/api/auth/session")
        assert resp.json() == {"authenticated": True}
