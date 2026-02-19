"""Regression tests for ingredient-only score caps and nutrition_used flag.

Validates that:
- Ingredient-only scores are conservatively capped (≤70, never grade A).
- nutrition_used / nutrition_confidence are set correctly.
- Nutrition-present products are unaffected by ingredient-only caps.
- UPF penalties scale up properly in ingredient-only mode.
"""

import pytest
from app.services.scorer import calculate_product_score


# ── Ingredient-only caps ──────────────────────────────────────────────────

class TestIngredientOnlyCaps:
    """Score ceiling and grade cap when nutrition is absent."""

    def test_score_capped_at_70_with_upf_signal(self):
        """Any ingredient-only product with ≥1 UPF signal must score ≤70."""
        result = calculate_product_score(
            ingredients=["water", "sugar", "natural flavors", "citric acid"],
        )
        assert result["score"] <= 70, (
            f"Ingredient-only with UPF signal should be ≤70, got {result['score']}"
        )
        assert result["grade"] != "A"

    def test_clean_ingredients_capped_at_70(self):
        """Even clean ingredients cannot exceed 70 without nutrition."""
        result = calculate_product_score(
            ingredients=["water", "oats", "almonds", "salt"],
        )
        assert result["score"] <= 70
        assert result["grade"] != "A"

    def test_grade_never_A_without_nutrition(self):
        """Grade must never be A when nutrition_used is False."""
        result = calculate_product_score(
            ingredients=["water"],
        )
        assert result["grade"] != "A"
        assert result["score"] <= 70

    def test_nutrition_used_false_when_none(self):
        result = calculate_product_score(
            ingredients=["wheat flour", "water", "salt"],
        )
        assert result["nutrition_used"] is False
        assert result["nutrition_confidence"] == "low"

    def test_nutrition_used_false_with_insufficient_fields(self):
        """If nutrition exists but < 2 key fields, treat as missing."""
        nut = {"energy_kcal_100g": 100}  # only 1 key field
        result = calculate_product_score(
            ingredients=["wheat flour", "water", "salt"],
            nutrition=nut,
        )
        assert result["nutrition_used"] is False
        assert result["nutrition_confidence"] == "low"
        assert result["score"] <= 70

    def test_uncertainty_message_present(self):
        result = calculate_product_score(
            ingredients=["sugar", "wheat flour", "palm oil"],
        )
        assert any(
            "nutrition facts not available" in u.lower()
            for u in result["uncertainties"]
        ), "Should include nutrition-missing uncertainty message"


# ── Nutrition-present (no caps) ───────────────────────────────────────────

class TestNutritionPresent:
    """Verify caps do NOT apply when nutrition is used."""

    def test_water_with_nutrition_scores_high(self):
        """Water + full nutrition should score ≥90 and grade A."""
        nut = {
            "energy_kcal_100g": 0,
            "sugars_g_100g": 0,
            "sat_fat_g_100g": 0,
            "sodium_mg_100g": 5,
            "fiber_g_100g": 0,
            "protein_g_100g": 0,
        }
        result = calculate_product_score(
            ingredients=["water"],
            nutrition=nut,
        )
        assert result["score"] >= 90, (
            f"Water with nutrition should score ≥90, got {result['score']}"
        )
        assert result["grade"] == "A"
        assert result["nutrition_used"] is True
        assert result["nutrition_confidence"] == "high"

    def test_nutrition_used_true_with_enough_fields(self):
        """2+ key nutrition fields → nutrition_used=True."""
        nut = {"sugars_g_100g": 5, "sodium_mg_100g": 100}
        result = calculate_product_score(
            ingredients=["wheat flour", "water"],
            nutrition=nut,
        )
        assert result["nutrition_used"] is True
        assert result["nutrition_confidence"] == "high"

    def test_coke_like_nutrition_scores_low(self):
        """Coke-like nutrition should score ≤55."""
        nut = {
            "energy_kcal_100g": 42,
            "sugars_g_100g": 10.6,
            "sat_fat_g_100g": 0,
            "sodium_mg_100g": 13,
            "fiber_g_100g": 0,
            "protein_g_100g": 0,
        }
        result = calculate_product_score(
            ingredients=["carbonated water", "sugar", "caramel color",
                         "phosphoric acid", "natural flavors", "caffeine"],
            nutrition=nut,
            product_name="Coca-Cola",
            product_categories=["en:sodas"],
        )
        assert result["score"] <= 55, (
            f"Coke-like nutrition should score ≤55, got {result['score']}"
        )
        assert result["nutrition_used"] is True

    def test_healthy_food_no_cap(self):
        """Healthy food with nutrition should not be capped at 70."""
        nut = {
            "energy_kcal_100g": 50,
            "sugars_g_100g": 0.5,
            "sat_fat_g_100g": 0.1,
            "sodium_mg_100g": 10,
            "fiber_g_100g": 6,
            "protein_g_100g": 10,
        }
        result = calculate_product_score(
            ingredients=["whole grain oats", "water"],
            nutrition=nut,
        )
        assert result["score"] > 70, (
            f"Healthy food with nutrition should score >70, got {result['score']}"
        )
        assert result["nutrition_used"] is True


# ── UPF penalty scaling in ingredient-only mode ──────────────────────────

class TestUPFIngredientOnly:
    """Verify boosted UPF penalties when nutrition is missing."""

    def test_modified_starch_significant_penalty(self):
        """Modified starch should create a meaningful penalty."""
        result = calculate_product_score(
            ingredients=["water", "modified food starch", "sugar", "salt"],
        )
        upf_lines = [p for p in result["penalties"] if "modified starch" in p.lower()]
        assert len(upf_lines) > 0, "Modified starch should produce UPF penalty line"

    def test_preservatives_add_up(self):
        """Multiple preservatives should produce meaningful total penalty."""
        result = calculate_product_score(
            ingredients=["water", "sugar", "sodium benzoate",
                         "potassium sorbate", "bht"],
        )
        upf_lines = [p for p in result["penalties"] if "preservative" in p.lower()]
        assert len(upf_lines) >= 2, (
            f"Expected ≥2 preservative penalty lines, got {len(upf_lines)}"
        )

    def test_heavy_upf_ingredient_only_scores_very_low(self):
        """Heavily processed ingredient-only product should score well below cap."""
        result = calculate_product_score(
            ingredients=[
                "sugar", "modified corn starch", "hydrogenated oil",
                "artificial flavor", "red 40", "yellow 5",
                "sodium benzoate", "aspartame", "maltodextrin",
            ],
        )
        assert result["score"] <= 50, (
            f"Heavily processed ingredient-only should score ≤50, got {result['score']}"
        )
        assert result["grade"] in ("C", "D", "F")
