"""Regression tests for beverage detection and unified scoring.

Ensures:
- Cereals (Cinnamon Toast Crunch) are NEVER labeled as beverage.
- Coca-Cola IS labeled as beverage.
- Scoring uses ONE unified logic for all products (no beverage branch).
- Coke-like nutriments score ≤ 55 even without beverage mode.
- Water scores ≥ 90.
"""

import pytest
from app.services.scorer import (
    _is_beverage,
    _score_from_nutrition,
    calculate_product_score,
)


# ── _is_beverage detection ─────────────────────────────────────────


class TestBeverageDetectionStrict:
    """Beverage detection must be strict: category-only, with blocklist."""

    def test_cereal_not_beverage(self):
        """Cinnamon Toast Crunch should NEVER be classified as beverage."""
        is_bev, reason = _is_beverage(
            product_name="cinnamon toast crunch",
            categories=["breakfast cereals", "cereals"],
        )
        assert is_bev is False, f"Cereal wrongly classified as beverage: {reason}"

    def test_cereal_with_ambiguous_categories(self):
        """Even if a cereal somehow has a loose 'drink' substring, blocklist wins."""
        is_bev, reason = _is_beverage(
            categories=["breakfast cereals", "cereals", "snack"],
        )
        assert is_bev is False

    def test_coca_cola_is_beverage(self):
        is_bev, reason = _is_beverage(
            categories=["beverages", "carbonated drinks", "sodas"],
        )
        assert is_bev is True
        assert "carbonated drinks" in reason or "beverages" in reason or "sodas" in reason

    def test_sparkling_water_is_beverage(self):
        is_bev, reason = _is_beverage(
            categories=["waters", "mineral waters"],
        )
        assert is_bev is True

    def test_orange_juice_is_beverage(self):
        is_bev, reason = _is_beverage(
            categories=["juices", "fruit juices"],
        )
        assert is_bev is True

    def test_energy_drink_is_beverage(self):
        is_bev, reason = _is_beverage(
            categories=["energy drinks", "beverages"],
        )
        assert is_bev is True

    def test_bread_not_beverage(self):
        is_bev, _ = _is_beverage(
            categories=["bread", "whole wheat bread"],
        )
        assert is_bev is False

    def test_chocolate_not_beverage(self):
        is_bev, _ = _is_beverage(
            categories=["chocolate", "candy bars"],
        )
        assert is_bev is False

    def test_yogurt_not_beverage(self):
        is_bev, _ = _is_beverage(
            categories=["yogurt", "dairy"],
        )
        assert is_bev is False

    def test_no_categories_not_beverage(self):
        """Missing categories → not beverage."""
        is_bev, _ = _is_beverage(categories=None)
        assert is_bev is False

    def test_empty_categories_not_beverage(self):
        is_bev, _ = _is_beverage(categories=[])
        assert is_bev is False

    def test_nutrition_heuristic_removed(self):
        """Nutrition-based detection should NOT be used (the old bug)."""
        # Low protein, low fiber, has sugar — was previously mis-detected
        is_bev, _ = _is_beverage(
            product_name="cinnamon toast crunch",
            categories=["breakfast cereals"],
            nutrition={
                "protein_g_100g": 0.5,
                "fiber_g_100g": 0.5,
                "sugars_g_100g": 10.0,
            },
        )
        assert is_bev is False

    def test_name_alone_does_not_trigger(self):
        """Product name should NOT trigger beverage detection anymore."""
        is_bev, _ = _is_beverage(
            product_name="cola flavored candy",
            categories=["candy"],
        )
        assert is_bev is False


# ── Unified scoring (no beverage branch) ───────────────────────────


class TestUnifiedScoring:
    """_score_from_nutrition uses ONE tier set — no is_bev parameter."""

    def test_score_from_nutrition_no_bev_param(self):
        """_score_from_nutrition should NOT accept an is_bev parameter."""
        import inspect
        sig = inspect.signature(_score_from_nutrition)
        param_names = list(sig.parameters.keys())
        assert "is_bev" not in param_names, (
            "_score_from_nutrition should not have an is_bev parameter"
        )

    def test_same_nutrition_same_score(self):
        """Same nutrition → same score, regardless of product type."""
        nut = {
            "energy_kcal_100g": 42,
            "sugars_g_100g": 10.6,
            "sat_fat_g_100g": 0.0,
            "sodium_mg_100g": 13,
            "fiber_g_100g": 0,
            "protein_g_100g": 0,
        }
        cola_result = calculate_product_score(
            ingredients=["carbonated water", "sugar"],
            nutrition=nut,
            product_name="Coca-Cola",
            product_categories=["beverages", "sodas"],
        )
        cereal_result = calculate_product_score(
            ingredients=["wheat", "sugar"],
            nutrition=nut,
            product_name="Some Cereal",
            product_categories=["breakfast cereals"],
        )
        assert cola_result["score"] == cereal_result["score"], (
            f"Same nutrition should give same score: "
            f"cola={cola_result['score']} vs cereal={cereal_result['score']}"
        )


# ── Strict scoring thresholds ─────────────────────────────────────


class TestStrictScoringThresholds:
    """Scoring must be strict enough without beverage mode."""

    def test_coke_nutriments_max_55(self):
        """Coke (14.6g sugar, 53.5 kcal) should score ≤ 55 even unified."""
        result = calculate_product_score(
            ingredients=["carbonated water", "sugar", "caramel color"],
            nutrition={
                "energy_kcal_100g": 53.5,
                "sugars_g_100g": 14.6,
                "sat_fat_g_100g": 0.0,
                "sodium_mg_100g": 17,
                "fiber_g_100g": 0,
                "protein_g_100g": 0,
            },
            product_name="Coca-Cola",
            product_categories=["beverages", "sodas"],
        )
        assert result["score"] <= 55, f"Coke scored {result['score']}, expected ≤ 55"
        assert result["grade"] not in ("A", "B")

    def test_coke_standard_sugar_max_70(self):
        """Coke (10.6g sugar, 42 kcal) with unified scoring."""
        result = calculate_product_score(
            ingredients=["carbonated water", "sugar"],
            nutrition={
                "energy_kcal_100g": 42,
                "sugars_g_100g": 10.6,
                "sat_fat_g_100g": 0,
                "sodium_mg_100g": 13,
                "fiber_g_100g": 0,
                "protein_g_100g": 0,
            },
        )
        assert result["score"] <= 70, f"Coke scored {result['score']}, expected ≤ 70"

    def test_water_min_90(self):
        """Plain water should score ≥ 90."""
        result = calculate_product_score(
            ingredients=["water"],
            nutrition={
                "energy_kcal_100g": 0,
                "sugars_g_100g": 0,
                "sat_fat_g_100g": 0,
                "sodium_mg_100g": 5,
                "fiber_g_100g": 0,
                "protein_g_100g": 0,
            },
            product_name="Water",
        )
        assert result["score"] >= 90, f"Water scored {result['score']}, expected ≥ 90"
        assert result["grade"] == "A"


# ── Beverage label in output ───────────────────────────────────────


class TestBeverageLabelOutput:
    """calculate_product_score should return beverage_label and beverage_reason."""

    def test_cola_has_beverage_label(self):
        result = calculate_product_score(
            ingredients=["carbonated water", "sugar"],
            product_categories=["beverages", "sodas"],
        )
        assert result["beverage_label"] is True
        assert result["beverage_reason"] != ""

    def test_cereal_no_beverage_label(self):
        result = calculate_product_score(
            ingredients=["wheat", "sugar"],
            product_categories=["breakfast cereals"],
        )
        assert result["beverage_label"] is False
        assert result["beverage_reason"] == ""

    def test_no_categories_no_beverage_label(self):
        result = calculate_product_score(
            ingredients=["water", "salt"],
        )
        assert result["beverage_label"] is False
