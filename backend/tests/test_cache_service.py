"""Tests for barcode-based cache service."""

import json
import pytest
from sqlalchemy import create_engine
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


# ── In-memory DB fixture ─────────────────────────────────────────
@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


# ── Basic round-trip ─────────────────────────────────────────────
class TestCacheRoundTrip:
    def test_upsert_then_get_returns_same_barcode(self, db):
        payload = {
            "product_name": "Test Oats",
            "brand": "TestBrand",
            "source": "label_photo",
            "ingredients_text": "oats, sugar, salt",
            "ingredients": [
                {"name_raw": "oats", "name_canonical": "oats"},
                {"name_raw": "sugar", "name_canonical": "sugar"},
            ],
            "nutrition_per_serving": {"calories": 150, "sodium_mg": 200},
            "nutrition_100g": {"energy_kcal_100g": 350, "sugars_g_100g": 12},
            "product_score": {"score": 72, "grade": "B"},
            "nutrition_confidence": "medium",
            "extraction_confidence": 0.85,
            "schema_version": SCHEMA_VERSION,
            "scoring_version": SCORING_VERSION,
        }

        upsert_cache_for_barcode(db, "1234567890", payload)
        cached = get_cached_by_barcode(db, "1234567890")

        assert cached is not None
        assert cached["barcode"] == "1234567890"
        assert cached["product_name"] == "Test Oats"
        assert cached["brand"] == "TestBrand"
        assert cached["source"] == "label_photo"
        assert cached["ingredients_text"] == "oats, sugar, salt"
        assert cached["nutrition_confidence"] == "medium"
        assert cached["extraction_confidence"] == pytest.approx(0.85)
        assert cached["schema_version"] == SCHEMA_VERSION
        assert cached["scoring_version"] == SCORING_VERSION

    def test_upsert_then_get_parses_json_fields(self, db):
        payload = {
            "ingredients": [{"name_raw": "water", "name_canonical": "water"}],
            "nutrition_per_serving": {"calories": 0, "sodium_mg": 5},
            "nutrition_100g": {"energy_kcal_100g": 0, "sodium_mg_100g": 14},
            "product_score": {"score": 90, "grade": "A"},
        }
        upsert_cache_for_barcode(db, "0000000001", payload)
        cached = get_cached_by_barcode(db, "0000000001")

        assert isinstance(cached["ingredients"], list)
        assert cached["ingredients"][0]["name_canonical"] == "water"
        assert isinstance(cached["nutrition_100g"], dict)
        assert cached["nutrition_100g"]["energy_kcal_100g"] == 0
        assert cached["product_score"]["score"] == 90

    def test_get_nonexistent_returns_none(self, db):
        assert get_cached_by_barcode(db, "9999999999") is None

    def test_upsert_updates_existing_row(self, db):
        upsert_cache_for_barcode(db, "1111111111", {
            "product_name": "V1",
            "ingredients_text": "sugar",
        })
        upsert_cache_for_barcode(db, "1111111111", {
            "product_name": "V2",
            "ingredients_text": "sugar, salt",
        })
        cached = get_cached_by_barcode(db, "1111111111")
        assert cached["product_name"] == "V2"
        assert cached["ingredients_text"] == "sugar, salt"

        # Only one row should exist
        count = db.query(ProductCache).filter(ProductCache.barcode == "1111111111").count()
        assert count == 1


# ── Usable nutrition detection ───────────────────────────────────
class TestCacheHasUsableNutrition:
    def test_usable_with_100g_fields(self):
        cached = {
            "nutrition_100g": {
                "energy_kcal_100g": 250,
                "sugars_g_100g": 10,
            },
            "nutrition_per_serving": {},
        }
        assert cache_has_usable_nutrition(cached) is True

    def test_usable_with_per_serving_fields(self):
        cached = {
            "nutrition_100g": {},
            "nutrition_per_serving": {
                "calories": 150,
                "sodium_mg": 200,
            },
        }
        assert cache_has_usable_nutrition(cached) is True

    def test_not_usable_with_only_one_field(self):
        cached = {
            "nutrition_100g": {"energy_kcal_100g": 250},
            "nutrition_per_serving": {"calories": 150},
        }
        assert cache_has_usable_nutrition(cached) is False

    def test_not_usable_with_empty_dicts(self):
        cached = {
            "nutrition_100g": {},
            "nutrition_per_serving": {},
        }
        assert cache_has_usable_nutrition(cached) is False

    def test_not_usable_with_none_values(self):
        cached = {
            "nutrition_100g": {"energy_kcal_100g": None, "sugars_g_100g": None},
            "nutrition_per_serving": None,
        }
        assert cache_has_usable_nutrition(cached) is False

    def test_handles_json_string_fields(self):
        cached = {
            "nutrition_100g": json.dumps({"energy_kcal_100g": 300, "sugars_g_100g": 5}),
            "nutrition_per_serving": "{}",
        }
        assert cache_has_usable_nutrition(cached) is True


# ── Scoring version ──────────────────────────────────────────────
class TestScoringVersioning:
    def test_scoring_version_stored(self, db):
        upsert_cache_for_barcode(db, "2222222222", {
            "scoring_version": 42,
            "schema_version": 3,
        })
        cached = get_cached_by_barcode(db, "2222222222")
        assert cached["scoring_version"] == 42
        assert cached["schema_version"] == 3

    def test_outdated_scoring_version_detectable(self, db):
        """When cached scoring_version != current, caller should recompute."""
        upsert_cache_for_barcode(db, "3333333333", {
            "scoring_version": SCORING_VERSION - 1 if SCORING_VERSION > 1 else 999,
            "ingredients_text": "sugar, water",
            "nutrition_100g": {"energy_kcal_100g": 200, "sugars_g_100g": 30},
        })
        cached = get_cached_by_barcode(db, "3333333333")
        assert cached["scoring_version"] != SCORING_VERSION
