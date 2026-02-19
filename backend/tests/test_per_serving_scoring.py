"""Tests for per-serving nutrition scoring and nutrition_used logic.

Validates that:
- Per-serving nutrition is used when per-100g is unavailable.
- DV%-based scoring produces strict penalties for high-sodium etc.
- Ingredient-only ceiling does NOT apply when per-serving nutrition exists.
- Generic oils (sunflower, canola) do not trigger emulsifier UPF signals.
- nutrition_used/nutrition_confidence are set correctly.
"""

import pytest
from app.services.scorer import (
    calculate_product_score,
    _has_usable_per_serving,
    _score_from_nutrition_per_serving,
    _detect_upf_tags,
)


# ── Per-serving scoring: Lunchables-style ─────────────────────────────────

class TestPerServingScoring:
    """DV%-based scoring for products with per-serving nutrition only."""

    def test_lunchables_style_scores_low(self):
        """High sodium per serving (780mg = 34% DV) should score ≤60, not A."""
        per_serving = {
            "calories": 360,
            "sodium_mg": 780,
            "saturated_fat_g": 3.5,
            "added_sugars_g": 1,
            "fiber_g": 1,
            "protein_g": 13,
        }
        result = calculate_product_score(
            ingredients=[
                "enriched flour", "water", "turkey breast", "cheddar cheese",
                "modified food starch", "sodium phosphate", "natural flavors",
            ],
            nutrition_per_serving=per_serving,
        )
        assert result["score"] <= 60, (
            f"Lunchables-style should score ≤60, got {result['score']}"
        )
        assert result["grade"] != "A"
        assert result["nutrition_used"] is True
        assert result["nutrition_confidence"] in ("medium", "high")
        # Should NOT have "Nutrition facts missing" uncertainty
        assert not any(
            "nutrition facts missing" in u.lower()
            for u in result["uncertainties"]
        )

    def test_water_per_serving_scores_high(self):
        """Water-like nutrition per serving should score ≥90."""
        per_serving = {
            "calories": 0,
            "sodium_mg": 5,
            "saturated_fat_g": 0,
            "total_sugars_g": 0,
        }
        result = calculate_product_score(
            ingredients=["water"],
            nutrition_per_serving=per_serving,
        )
        assert result["score"] >= 90, (
            f"Water per-serving should score ≥90, got {result['score']}"
        )
        assert result["nutrition_used"] is True

    def test_high_sodium_only_per_serving(self):
        """Very high sodium alone should significantly reduce score."""
        per_serving = {
            "calories": 200,
            "sodium_mg": 1200,  # 52% DV
        }
        result = calculate_product_score(
            ingredients=["water", "salt", "wheat flour"],
            nutrition_per_serving=per_serving,
        )
        assert result["score"] <= 55
        assert result["nutrition_used"] is True

    def test_per_serving_with_high_sugar(self):
        """High added sugars per serving should reduce score."""
        per_serving = {
            "calories": 250,
            "sodium_mg": 100,
            "added_sugars_g": 30,  # 60% DV
        }
        result = calculate_product_score(
            ingredients=["sugar", "wheat flour", "butter"],
            nutrition_per_serving=per_serving,
        )
        assert result["score"] <= 50
        assert any("sugar" in r.lower() for r in result["reasons"])


# ── nutrition_used logic ──────────────────────────────────────────────────

class TestNutritionUsedLogic:
    """Test that nutrition_used is properly determined."""

    def test_per_serving_makes_nutrition_used_true(self):
        """nutrition_100g=None but per-serving has enough fields → nutrition_used=True."""
        per_serving = {"calories": 200, "sodium_mg": 400}
        result = calculate_product_score(
            ingredients=["wheat flour", "water", "salt"],
            nutrition_per_serving=per_serving,
        )
        assert result["nutrition_used"] is True
        assert result["score"] <= 100  # no ceiling at 70
        assert not any(
            "nutrition facts missing" in u.lower()
            for u in result["uncertainties"]
        )

    def test_no_ceiling_with_per_serving(self):
        """Ingredient-only ceiling must NOT apply when per-serving exists."""
        per_serving = {
            "calories": 10,
            "sodium_mg": 5,
            "saturated_fat_g": 0,
            "total_sugars_g": 0,
        }
        result = calculate_product_score(
            ingredients=["whole grain oats", "water"],
            nutrition_per_serving=per_serving,
        )
        # Should be able to exceed 70 (the ingredient-only ceiling)
        assert result["score"] > 70
        assert result["nutrition_used"] is True

    def test_both_missing_applies_ceiling(self):
        """When both per-100g and per-serving are None → ceiling applies."""
        result = calculate_product_score(
            ingredients=["wheat flour", "water", "salt"],
        )
        assert result["nutrition_used"] is False
        assert result["score"] <= 70
        assert result["grade"] != "A"
        assert any(
            "nutrition facts" in u.lower()
            for u in result["uncertainties"]
        )

    def test_per_100g_preferred_over_per_serving(self):
        """When per-100g exists, it should be used (not per-serving)."""
        nut_100g = {
            "energy_kcal_100g": 42,
            "sugars_g_100g": 10.6,
            "sat_fat_g_100g": 0,
            "sodium_mg_100g": 13,
        }
        per_serving = {
            "calories": 0,
            "sodium_mg": 0,
        }
        result = calculate_product_score(
            ingredients=["water", "sugar"],
            nutrition=nut_100g,
            nutrition_per_serving=per_serving,
        )
        assert result["nutrition_used"] is True
        assert result["nutrition_confidence"] == "high"
        # Score should reflect per-100g penalties (sugar 10.6g → penalty),
        # NOT the zero per-serving values
        assert result["score"] < 90

    def test_insufficient_per_serving_falls_to_ingredient_only(self):
        """Per-serving with only 1 field is not usable."""
        per_serving = {"calories": 100}
        result = calculate_product_score(
            ingredients=["wheat flour", "water"],
            nutrition_per_serving=per_serving,
        )
        assert result["nutrition_used"] is False
        assert result["score"] <= 70

    def test_nutrition_confidence_medium_for_per_serving(self):
        """Per-serving path should set nutrition_confidence=medium."""
        per_serving = {"calories": 200, "sodium_mg": 400}
        result = calculate_product_score(
            ingredients=["wheat flour", "water"],
            nutrition_per_serving=per_serving,
        )
        assert result["nutrition_confidence"] == "medium"

    def test_uncertainty_mentions_per_serving_normalization(self):
        """When per-serving is used, uncertainty should mention normalization issue."""
        per_serving = {"calories": 200, "sodium_mg": 400}
        result = calculate_product_score(
            ingredients=["wheat flour", "water"],
            nutrition_per_serving=per_serving,
        )
        assert any(
            "per serving" in u.lower()
            for u in result["uncertainties"]
        )


# ── _has_usable_per_serving helper ────────────────────────────────────────

class TestHasUsablePerServing:
    def test_none_returns_false(self):
        assert _has_usable_per_serving(None) is False

    def test_empty_dict_returns_false(self):
        assert _has_usable_per_serving({}) is False

    def test_one_field_returns_false(self):
        assert _has_usable_per_serving({"calories": 100}) is False

    def test_two_fields_returns_true(self):
        assert _has_usable_per_serving({"calories": 100, "sodium_mg": 200}) is True

    def test_many_fields_returns_true(self):
        assert _has_usable_per_serving({
            "calories": 200, "sodium_mg": 500,
            "saturated_fat_g": 3, "fiber_g": 4,
        }) is True


# ── Per-serving scoring function ──────────────────────────────────────────

class TestPerServingScoringFunction:
    def test_zero_nutrition_scores_100(self):
        score, reasons, penalties = _score_from_nutrition_per_serving({
            "calories": 0, "sodium_mg": 0, "saturated_fat_g": 0, "added_sugars_g": 0,
        })
        assert score == 100

    def test_high_sodium_reduces_score(self):
        score, reasons, penalties = _score_from_nutrition_per_serving({
            "calories": 0, "sodium_mg": 1000,
        })
        # 1000/2300 ≈ 43% DV, penalty = 0.9 * 43 ≈ 39
        assert score <= 65
        assert any("sodium" in p.lower() for p in penalties)

    def test_fiber_protein_credits_capped(self):
        score, reasons, penalties = _score_from_nutrition_per_serving({
            "calories": 0, "sodium_mg": 0,
            "fiber_g": 20, "protein_g": 30,
        })
        # Credits capped at 10, score should be 100 (already at max)
        assert score == 100


# ── Emulsifier false positive fix ─────────────────────────────────────────

class TestEmulsifierFalsePositives:
    """Generic oils should NOT trigger emulsifier UPF signal."""

    def test_sunflower_oil_no_emulsifier(self):
        tags = _detect_upf_tags("sunflower oil")
        assert "upf_indicator_emulsifier" not in tags

    def test_high_oleic_sunflower_oil_no_emulsifier(self):
        tags = _detect_upf_tags("high oleic sunflower oil")
        assert "upf_indicator_emulsifier" not in tags

    def test_canola_oil_no_emulsifier(self):
        tags = _detect_upf_tags("canola oil")
        assert "upf_indicator_emulsifier" not in tags

    def test_soybean_oil_no_emulsifier(self):
        tags = _detect_upf_tags("soybean oil")
        assert "upf_indicator_emulsifier" not in tags

    def test_soy_lecithin_still_emulsifier(self):
        """Actual emulsifier terms should still trigger."""
        tags = _detect_upf_tags("soy lecithin")
        assert "upf_indicator_emulsifier" in tags

    def test_mono_diglycerides_still_emulsifier(self):
        tags = _detect_upf_tags("mono- and diglycerides")
        assert "upf_indicator_emulsifier" in tags

    def test_sunflower_oil_no_emulsifier_in_scoring(self):
        """Full score pipeline: sunflower oil should not produce emulsifier penalty."""
        result = calculate_product_score(
            ingredients=["wheat flour", "water", "sunflower oil", "salt"],
        )
        emulsifier_lines = [
            p for p in result["penalties"] if "emulsifier" in p.lower()
        ]
        assert len(emulsifier_lines) == 0, (
            f"Sunflower oil should not create emulsifier penalty, got: {emulsifier_lines}"
        )
