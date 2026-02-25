"""Tests for Profile CRUD endpoints and auth integration.

These tests mock the auth dependency so we don't need a real Supabase instance.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.database import engine, Base, get_db
from app.auth import AuthUser, get_current_user, get_optional_user
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Isolated test DB ────────────────────────────
TEST_DB_URL = "sqlite:///./test_profiles.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


MOCK_USER = AuthUser(user_id="user-abc-123", email="test@example.com")
MOCK_USER_B = AuthUser(user_id="user-xyz-456", email="other@example.com")


def override_get_current_user():
    return MOCK_USER


def override_get_optional_user():
    return MOCK_USER


# ── Setup/teardown ──────────────────────────────
@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables fresh for each test."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_optional_user] = override_get_optional_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ═══════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════

class TestProfileCRUD:
    """Profile create / read / update / delete."""

    def test_empty_profiles(self, client):
        res = client.get("/api/profiles")
        assert res.status_code == 200
        assert res.json() == []

    def test_create_profile(self, client):
        res = client.post("/api/profiles", json={
            "name": "Mom",
            "allergies": ["peanuts"],
            "diet_style": "vegetarian",
        })
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Mom"
        assert data["allergies"] == ["peanuts"]
        assert data["diet_style"] == "vegetarian"
        assert data["is_default"] is True  # first profile is auto-default

    def test_first_profile_auto_default(self, client):
        res = client.post("/api/profiles", json={"name": "Kid", "is_default": False})
        assert res.status_code == 201
        assert res.json()["is_default"] is True  # forced to True

    def test_list_profiles(self, client):
        client.post("/api/profiles", json={"name": "A"})
        client.post("/api/profiles", json={"name": "B"})  # will fail due to free-tier limit
        res = client.get("/api/profiles")
        assert res.status_code == 200
        # Free tier only allows 1 profile
        assert len(res.json()) == 1

    def test_free_tier_limit(self, client):
        """Free tier = 1 profile max."""
        client.post("/api/profiles", json={"name": "First"})
        res = client.post("/api/profiles", json={"name": "Second"})
        assert res.status_code == 403
        assert "limit" in res.json()["detail"].lower()

    def test_update_profile(self, client):
        create = client.post("/api/profiles", json={"name": "Original"})
        pid = create.json()["id"]

        res = client.patch(f"/api/profiles/{pid}", json={
            "name": "Updated",
            "allergies": ["milk", "soy"],
        })
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Updated"
        assert data["allergies"] == ["milk", "soy"]

    def test_delete_profile(self, client):
        create = client.post("/api/profiles", json={"name": "Temp"})
        pid = create.json()["id"]

        res = client.delete(f"/api/profiles/{pid}")
        assert res.status_code == 204

        res = client.get("/api/profiles")
        assert len(res.json()) == 0

    def test_delete_nonexistent(self, client):
        res = client.delete("/api/profiles/nonexistent-id")
        assert res.status_code == 404

    def test_update_nonexistent(self, client):
        res = client.patch("/api/profiles/nonexistent-id", json={"name": "x"})
        assert res.status_code == 404


class TestProfileIsolation:
    """User A cannot see or modify User B's profiles."""

    def test_cross_user_invisible(self, client):
        # User A creates a profile
        res_a = client.post("/api/profiles", json={"name": "A-Profile"})
        assert res_a.status_code == 201

        # Switch to user B
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER_B
        app.dependency_overrides[get_optional_user] = lambda: MOCK_USER_B

        # User B should see zero profiles
        res_b = client.get("/api/profiles")
        assert res_b.status_code == 200
        assert len(res_b.json()) == 0

    def test_cross_user_update_denied(self, client):
        res_a = client.post("/api/profiles", json={"name": "A-Only"})
        pid = res_a.json()["id"]

        # Switch to user B
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER_B

        # User B cannot update A's profile
        res_b = client.patch(f"/api/profiles/{pid}", json={"name": "Hacked"})
        assert res_b.status_code == 404

    def test_cross_user_delete_denied(self, client):
        res_a = client.post("/api/profiles", json={"name": "A-Only"})
        pid = res_a.json()["id"]

        # Switch to user B
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER_B

        res_b = client.delete(f"/api/profiles/{pid}")
        assert res_b.status_code == 404


class TestSetDefault:
    """POST /api/profiles/{id}/default."""

    def test_set_default_not_found(self, client):
        res = client.post("/api/profiles/bad-id/default")
        assert res.status_code == 404


class TestProfileSchemas:
    """Validate schema round-trip."""

    def test_profile_response_fields(self, client):
        res = client.post("/api/profiles", json={
            "name": "Test",
            "allergies": ["a"],
            "avoid_terms": ["b"],
            "diet_style": "vegan",
        })
        data = res.json()
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["diet_style"] == "vegan"
