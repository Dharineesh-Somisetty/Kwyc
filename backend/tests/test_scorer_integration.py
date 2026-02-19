"""Tests for the nutrition-first product scoring engine."""

import pytest
from app.services.scorer import calculate_product_score


# ── Basic contract ─────────────────────────────────────────────────
class TestScoreContract:
    def test_score_in_valid_range(self):
        result = calculate_product_score(["sugar", "water", "citric acid"])
        assert 0 <= result["score"] <= 100

    def test_grade_is_valid(self):
        result = calculate_product_score(["water", "salt"])
        assert result["grade"] in ("A", "B", "C", "D", "F")

    def test_result_has_all_keys(self):
        result = calculate_product_score(["water"])
        for key in ("score", "grade", "reasons", "penalties", "uncertainties",
                     "personalized_conflicts", "nutrition_used",
                     "nutrition_confidence",
                     "beverage_label", "beverage_reason"):
            assert key in result

    def test_empty_everything_returns_default(self):
        result = calculate_product_score([])
        assert result["score"] == 50
        assert result["grade"] == "C"


# ── Nutrition-based scoring ────────────────────────────────────────
class TestNutritionScoring:
    """Test primary path: score from per-100g nutrition data."""

    def test_coke_like_scores_low(self):
        """Coca-Cola-like nutrition: ~42 kcal, ~10.6g sugar, ~13mg sodium."""
        nut = {
            "energy_kcal_100g": 42,
            "sugars_g_100g": 10.6,
            "sat_fat_g_100g": 0,
            "sodium_mg_100g": 13,
            "fiber_g_100g": 0,
            "protein_g_100g": 0,
        }
        result = calculate_product_score(
            ["carbonated water", "sugar", "caramel color", "phosphoric acid", "natural flavors", "caffeine"],
            nutrition=nut,
            product_name="Coca-Cola",
            product_categories=["en:sodas"],
        )
        # Unified scoring (no beverage branch) — 10.6g sugar is moderate
        assert result["score"] <= 70, f"Coke should score ≤70, got {result['score']}"
        assert result["grade"] != "A"

    def test_nutella_like_high_sugar(self):
        """Nutella-like: very high sugar ~56g, high sat fat ~10.6g."""
        nut = {
            "energy_kcal_100g": 539,
            "sugars_g_100g": 56.3,
            "sat_fat_g_100g": 10.6,
            "sodium_mg_100g": 41,
            "fiber_g_100g": 3.4,
            "protein_g_100g": 6.3,
        }
        result = calculate_product_score(
            ["sugar", "palm oil", "hazelnuts", "cocoa", "skim milk", "whey", "lecithin", "vanillin"],
            nutrition=nut,
            product_name="Nutella",
        )
        assert result["score"] <= 40, f"Nutella-like should score ≤40, got {result['score']}"
        assert result["grade"] in ("D", "F")

    def test_healthy_food_scores_high(self):
        """Plain oats: low sugar, good fiber, good protein."""
        nut = {
            "energy_kcal_100g": 375,
            "sugars_g_100g": 1.0,
            "sat_fat_g_100g": 1.2,
            "sodium_mg_100g": 6,
            "fiber_g_100g": 10.0,
            "protein_g_100g": 13.0,
        }
        result = calculate_product_score(
            ["whole grain oats"],
            nutrition=nut,
            product_name="Rolled Oats",
        )
        assert result["score"] >= 70, f"Oats should score ≥70, got {result['score']}"

    def test_unified_scoring_same_nutrition_same_score(self):
        """Same nutrition → same score regardless of product type (unified scoring)."""
        nut = {
            "sugars_g_100g": 10.0,
            "energy_kcal_100g": 45,
        }
        bev = calculate_product_score(
            ["water", "sugar"], nutrition=nut, product_name="Lemonade",
        )
        food = calculate_product_score(
            ["flour", "sugar"], nutrition=nut, product_name="Bread",
        )
        assert bev["score"] == food["score"], (
            f"Unified scoring: same nutrition must give same score, "
            f"got bev={bev['score']} vs food={food['score']}"
        )

    def test_nutrition_overrides_ingredient_fallback(self):
        """When nutrition is present, ingredient-only uncertainties should NOT appear."""
        nut = {"sugars_g_100g": 5.0, "energy_kcal_100g": 200}
        result = calculate_product_score(["water", "sugar"], nutrition=nut)
        assert not any("ingredient analysis only" in u for u in result["uncertainties"])


# ── Ingredient-only fallback ───────────────────────────────────────
class TestIngredientFallback:
    def test_no_nutrition_adds_uncertainty(self):
        result = calculate_product_score(["water", "sugar", "citric acid"])
        assert any("ingredient" in u.lower() or "nutrition" in u.lower() for u in result["uncertainties"])

    def test_hfcs_in_top3_penalised(self):
        result = calculate_product_score([
            "water", "high fructose corn syrup", "citric acid",
        ])
        # Sugar proxy -25, then capped at 70 → should be well under 70
        assert result["score"] <= 70
        assert any("sugar" in r.lower() for r in result["reasons"])

    def test_clean_ingredients_scores_within_cap(self):
        result = calculate_product_score(["water", "oats", "almonds"])
        # Without nutrition, score is capped at 70
        assert result["score"] <= 70
        assert result["score"] >= 60


# ── Personalization overlay ────────────────────────────────────────
class TestPersonalization:
    def test_allergy_conflict_returns_zero(self):
        profile = {"allergies": ["milk"]}
        result = calculate_product_score(
            ["whole milk powder", "sugar"],
            user_profile=profile,
        )
        assert result["score"] == 0
        assert result["grade"] == "F"
        assert len(result["personalized_conflicts"]) > 0

    def test_allergy_with_nutrition_still_zero(self):
        """Allergy should override even good nutrition."""
        nut = {"sugars_g_100g": 1.0, "energy_kcal_100g": 50}
        profile = {"allergies": ["peanut"]}
        result = calculate_product_score(
            ["rice", "peanut butter"],
            nutrition=nut,
            user_profile=profile,
        )
        assert result["score"] == 0

    def test_avoid_term_penalty(self):
        result = calculate_product_score(
            ["water", "palm oil", "sugar"],
            user_profile={"avoid_terms": ["palm oil"]},
        )
        assert any("palm oil" in c.lower() for c in result["personalized_conflicts"])
        # Should have been penalised
        assert result["score"] < 100

    def test_no_profile_no_conflicts(self):
        result = calculate_product_score(["water", "salt"])
        assert result["personalized_conflicts"] == []
