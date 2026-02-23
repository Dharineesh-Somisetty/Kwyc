"""Integration tests for ProductCache: database engine, fallback flow, cache hits.

Covers:
  - Postgres-ready engine creation (via monkeypatch, no real Postgres needed)
  - Full barcode → label-upload → re-scan flow simulating the cache lifecycle
  - Schema/scoring version mismatch detection
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ProductCache
from app.services.cache_service import (
    get_cached_by_barcode,
    upsert_cache_for_barcode,
    cache_has_usable_nutrition,
    SCHEMA_VERSION,
    SCORING_VERSION,
)


# ── In-memory SQLite fixture ─────────────────────────────────────
@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


# ══════════════════════════════════════════════════════════════════
# 1.  Postgres-ready engine creation (mock-based)
# ══════════════════════════════════════════════════════════════════

class TestDatabaseEngineCreation:
    """Verify that database.py builds the correct engine kwargs per backend."""

    def test_sqlite_url_includes_check_same_thread(self):
        """SQLite URL should produce connect_args with check_same_thread=False."""
        from app import database as db_mod

        # Default is sqlite, so _connect_args should be set
        assert "check_same_thread" in db_mod._connect_args
        assert db_mod._connect_args["check_same_thread"] is False

    def test_postgres_url_omits_check_same_thread(self):
        """When DATABASE_URL is Postgres, connect_args must be empty."""
        import importlib

        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://u:p@localhost:5432/test"}):
            # Re-import the module so it re-evaluates DATABASE_URL
            from app import database as db_mod
            importlib.reload(db_mod)

        # _connect_args should be empty dict for postgres
        assert db_mod._connect_args == {}

        # Restore SQLite default for other tests
        with patch.dict("os.environ", {"DATABASE_URL": "sqlite:///./labellens.db"}):
            importlib.reload(db_mod)


# ══════════════════════════════════════════════════════════════════
# 2.  Full barcode → label → cache-hit lifecycle
# ══════════════════════════════════════════════════════════════════

class TestBarcodeLabelFallbackFlow:
    """Simulates: barcode scan has OFF ingredients but no nutrition →
    user uploads label photo → cache populated → re-scan hits cache.
    """

    def test_label_upload_populates_cache(self, db):
        """After label upload with barcode, cache should contain extraction."""
        barcode = "5000159484695"

        # Step 1: No cache exists yet
        assert get_cached_by_barcode(db, barcode) is None

        # Step 2: Simulate label extraction result → upsert
        extraction_payload = {
            "product_name": "Coca-Cola Original",
            "brand": "Coca-Cola",
            "source": "label_photo",
            "ingredients_text": "carbonated water, sugar, colour (caramel E150d), phosphoric acid, natural flavourings including caffeine",
            "ingredients": [
                {"name_raw": "carbonated water", "name_canonical": "carbonated water"},
                {"name_raw": "sugar", "name_canonical": "sugar"},
                {"name_raw": "caramel E150d", "name_canonical": "caramel color"},
            ],
            "nutrition_per_serving": {
                "calories": 139,
                "total_sugars_g": 35,
                "sodium_mg": 10,
            },
            "nutrition_100g": {
                "energy_kcal_100g": 42,
                "sugars_g_100g": 10.6,
                "sodium_mg_100g": 3,
            },
            "product_score": {"score": 35, "grade": "D"},
            "nutrition_confidence": "high",
            "extraction_confidence": 0.92,
            "schema_version": SCHEMA_VERSION,
            "scoring_version": SCORING_VERSION,
        }
        upsert_cache_for_barcode(db, barcode, extraction_payload)

        # Step 3: Re-scan by barcode → cache hit
        cached = get_cached_by_barcode(db, barcode)
        assert cached is not None
        assert cached["barcode"] == barcode
        assert cached["source"] == "label_photo"
        assert cached["product_name"] == "Coca-Cola Original"
        assert cached["nutrition_confidence"] == "high"
        assert cache_has_usable_nutrition(cached) is True

    def test_rescan_uses_cached_nutrition(self, db):
        """Second barcode scan should find cached nutrition and skip OFF lookup."""
        barcode = "8901030793530"

        # Populate cache (simulating prior label upload)
        upsert_cache_for_barcode(db, barcode, {
            "product_name": "Maggi Noodles",
            "brand": "Nestlé",
            "source": "label_photo",
            "ingredients_text": "wheat flour, palm oil, salt, sugar",
            "ingredients": [
                {"name_raw": "wheat flour", "name_canonical": "wheat flour"},
                {"name_raw": "palm oil", "name_canonical": "palm oil"},
            ],
            "nutrition_per_serving": {"calories": 205, "sodium_mg": 860, "saturated_fat_g": 3.4},
            "nutrition_100g": {"energy_kcal_100g": 430, "sugars_g_100g": 2, "sodium_mg_100g": 1800, "sat_fat_g_100g": 7.1},
            "product_score": {"score": 42, "grade": "C"},
            "nutrition_confidence": "high",
            "extraction_confidence": 0.88,
            "schema_version": SCHEMA_VERSION,
            "scoring_version": SCORING_VERSION,
        })

        # Re-scan: cache should have usable nutrition
        cached = get_cached_by_barcode(db, barcode)
        assert cached is not None
        assert cache_has_usable_nutrition(cached) is True
        assert cached["nutrition_100g"]["energy_kcal_100g"] == 430
        assert cached["product_score"]["score"] == 42

    def test_cache_without_nutrition_is_not_usable(self, db):
        """Barcode with only ingredients (no nutrition) → not usable for scoring."""
        barcode = "0000000099"
        upsert_cache_for_barcode(db, barcode, {
            "product_name": "Unknown Snack",
            "ingredients_text": "sugar, starch, flavor",
            "ingredients": [{"name_raw": "sugar", "name_canonical": "sugar"}],
            # Deliberately omit nutrition_per_serving and nutrition_100g
        })

        cached = get_cached_by_barcode(db, barcode)
        assert cached is not None
        assert cache_has_usable_nutrition(cached) is False


# ══════════════════════════════════════════════════════════════════
# 3.  ProductCache model integrity
# ══════════════════════════════════════════════════════════════════

class TestProductCacheModel:
    """Verify ORM model constraints and defaults."""

    def test_barcode_is_primary_key(self, db):
        """Inserting two rows with same barcode should update, not duplicate."""
        upsert_cache_for_barcode(db, "PK_TEST_001", {"product_name": "First"})
        upsert_cache_for_barcode(db, "PK_TEST_001", {"product_name": "Second"})

        count = db.query(ProductCache).filter(ProductCache.barcode == "PK_TEST_001").count()
        assert count == 1
        assert get_cached_by_barcode(db, "PK_TEST_001")["product_name"] == "Second"

    def test_updated_at_auto_populates(self, db):
        """updated_at should be set automatically on insert."""
        upsert_cache_for_barcode(db, "TS_TEST_001", {"product_name": "Timestamps"})
        cached = get_cached_by_barcode(db, "TS_TEST_001")
        assert cached["updated_at"] is not None

    def test_all_json_fields_roundtrip(self, db):
        """All four JSON columns should serialize/deserialize correctly."""
        payload = {
            "ingredients": [{"name_raw": "a"}, {"name_raw": "b"}],
            "nutrition_per_serving": {"calories": 100, "sodium_mg": 50},
            "nutrition_100g": {"energy_kcal_100g": 200},
            "product_score": {"score": 80, "grade": "B", "penalties": [{"tag": "sugar", "penalty": 5}]},
        }
        upsert_cache_for_barcode(db, "JSON_RT_001", payload)
        cached = get_cached_by_barcode(db, "JSON_RT_001")

        assert cached["ingredients"] == payload["ingredients"]
        assert cached["nutrition_per_serving"] == payload["nutrition_per_serving"]
        assert cached["nutrition_100g"] == payload["nutrition_100g"]
        assert cached["product_score"]["penalties"][0]["penalty"] == 5

    def test_empty_payload_uses_defaults(self, db):
        """Upserting with no fields should use safe defaults, not crash."""
        upsert_cache_for_barcode(db, "EMPTY_001", {})
        cached = get_cached_by_barcode(db, "EMPTY_001")

        assert cached["product_name"] == ""
        assert cached["brand"] == ""
        assert cached["source"] == "label_photo"
        assert cached["ingredients"] == {}
        assert cached["nutrition_confidence"] == "low"
        assert cached["extraction_confidence"] == 0.0
        assert cached["schema_version"] == SCHEMA_VERSION
        assert cached["scoring_version"] == SCORING_VERSION


# ══════════════════════════════════════════════════════════════════
# 4.  Version mismatch detection
# ══════════════════════════════════════════════════════════════════

class TestVersionMismatch:
    """Callers should detect when cached scoring is stale and re-score."""

    def test_current_version_matches(self, db):
        upsert_cache_for_barcode(db, "V_MATCH", {
            "scoring_version": SCORING_VERSION,
            "schema_version": SCHEMA_VERSION,
        })
        cached = get_cached_by_barcode(db, "V_MATCH")
        assert cached["scoring_version"] == SCORING_VERSION
        assert cached["schema_version"] == SCHEMA_VERSION

    def test_stale_scoring_version_detected(self, db):
        stale = SCORING_VERSION + 100  # obviously different
        upsert_cache_for_barcode(db, "V_STALE", {"scoring_version": stale})
        cached = get_cached_by_barcode(db, "V_STALE")
        assert cached["scoring_version"] != SCORING_VERSION

    def test_stale_schema_version_detected(self, db):
        upsert_cache_for_barcode(db, "S_STALE", {"schema_version": SCHEMA_VERSION + 50})
        cached = get_cached_by_barcode(db, "S_STALE")
        assert cached["schema_version"] != SCHEMA_VERSION
