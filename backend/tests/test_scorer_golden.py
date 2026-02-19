"""Golden tests for the scoring engine.

Each test encodes a real-world product scenario with expected score bounds.
Uses GOLDEN_PRODUCTS parameterized fixtures for systematic coverage.
"""

import pytest
from app.services.scorer import (
    calculate_product_score,
    _is_beverage,
    position_weight,
)


# ── GOLDEN_PRODUCTS fixtures ───────────────────────────────────────────────

GOLDEN_PRODUCTS = {
    "cola_soda_like": {
        "ingredients": [
            "carbonated water", "sugar", "caramel color",
            "phosphoric acid", "natural flavors", "caffeine",
        ],
        "nutrition": {
            "energy_kcal_100g": 42,
            "sugars_g_100g": 10.6,
            "sat_fat_g_100g": 0.0,
            "sodium_mg_100g": 3.0,
            "fiber_g_100g": 0.0,
            "protein_g_100g": 0.0,
        },
        "categories": ["en:sodas", "en:beverages"],
        "product_name": "Coca-Cola",
        "expected_range": (0, 55),
        "not_grade": "A",
    },
    "sparkling_water": {
        "ingredients": ["carbonated water", "natural mineral salts"],
        "nutrition": {
            "energy_kcal_100g": 0,
            "sugars_g_100g": 0,
            "sat_fat_g_100g": 0,
            "sodium_mg_100g": 5,
            "fiber_g_100g": 0,
            "protein_g_100g": 0,
        },
        "categories": ["en:waters", "en:mineral-waters"],
        "product_name": "Sparkling Water",
        "expected_range": (90, 100),
        "expected_grade": "A",
    },
    "diet_soda_like": {
        "ingredients": [
            "carbonated water", "caramel color", "aspartame",
            "phosphoric acid", "potassium benzoate", "natural flavors",
            "acesulfame potassium", "caffeine",
        ],
        "nutrition": {
            "energy_kcal_100g": 1,
            "sugars_g_100g": 0.0,
            "sat_fat_g_100g": 0.0,
            "sodium_mg_100g": 12.0,
            "fiber_g_100g": 0.0,
            "protein_g_100g": 0.0,
        },
        "categories": ["en:sodas", "en:diet-soft-drinks"],
        "product_name": "Diet Soda",
        # Zero nutrition penalties; UPF cap=15 limits deduction.
        # Score ~85-90. Diet soda is nutritionally inert but processed.
        "expected_range": (80, 100),
    },
    "chocolate_hazelnut_spread_like": {
        "ingredients": [
            "sugar", "palm oil", "hazelnuts", "cocoa powder",
            "skim milk powder", "soy lecithin", "vanillin",
        ],
        "nutrition": {
            "energy_kcal_100g": 539,
            "sugars_g_100g": 56.3,
            "sat_fat_g_100g": 10.6,
            "sodium_mg_100g": 41,
            "fiber_g_100g": 3.4,
            "protein_g_100g": 6.3,
        },
        "categories": ["en:spreads", "en:chocolate-spreads"],
        "product_name": "Chocolate Hazelnut Spread",
        "expected_range": (0, 45),
        "not_grade": "A",
    },
    "plain_greek_yogurt_like": {
        "ingredients": ["milk", "cream", "live active cultures"],
        "nutrition": {
            "energy_kcal_100g": 97,
            "sugars_g_100g": 3.6,
            "sat_fat_g_100g": 3.0,
            "sodium_mg_100g": 47,
            "fiber_g_100g": 0.0,
            "protein_g_100g": 10.0,
        },
        "categories": ["en:yogurts", "en:greek-yogurt"],
        "product_name": "Plain Greek Yogurt",
        "expected_range": (65, 95),
    },
    "potato_chips_like": {
        "ingredients": [
            "potatoes", "vegetable oil", "salt",
        ],
        "nutrition": {
            "energy_kcal_100g": 536,
            "sugars_g_100g": 0.5,
            "sat_fat_g_100g": 3.5,
            "sodium_mg_100g": 500,
            "fiber_g_100g": 4.4,
            "protein_g_100g": 6.7,
        },
        "categories": ["en:snacks", "en:chips"],
        "product_name": "Potato Chips",
        "expected_range": (25, 65),
    },
    "high_fiber_cereal_like": {
        "ingredients": [
            "whole grain wheat", "sugar", "wheat bran",
            "corn starch", "salt", "vitamins and minerals",
        ],
        "nutrition": {
            "energy_kcal_100g": 340,
            "sugars_g_100g": 12.0,
            "sat_fat_g_100g": 0.5,
            "sodium_mg_100g": 280,
            "fiber_g_100g": 12.0,
            "protein_g_100g": 10.0,
        },
        "categories": ["en:breakfast-cereals"],
        "product_name": "High Fiber Cereal",
        # Strict sugar tier (>10g → −45) + energy (>300 → −28) + sodium (>240 → −12)
        # offset by fiber (+10) and protein (+5) = ~30
        "expected_range": (20, 45),
    },
    "allergy_hard_fail_milk": {
        "ingredients": ["sugar", "milk powder", "cocoa butter"],
        "nutrition": None,
        "categories": [],
        "product_name": "Chocolate Bar",
        "user_profile": {"allergies": ["milk"]},
        "expected_score": 0,
        "expected_grade": "F",
    },
}


def _score_product(key: str) -> dict:
    """Run scorer for a GOLDEN_PRODUCTS entry."""
    p = GOLDEN_PRODUCTS[key]
    return calculate_product_score(
        ingredients=p["ingredients"],
        nutrition=p.get("nutrition"),
        product_name=p.get("product_name"),
        product_categories=p.get("categories"),
        user_profile=p.get("user_profile"),
    )


# ── Parameterized golden tests ─────────────────────────────────────────────

@pytest.mark.parametrize("product_key", list(GOLDEN_PRODUCTS.keys()))
class TestGoldenProducts:
    def test_score_in_range(self, product_key):
        p = GOLDEN_PRODUCTS[product_key]
        result = _score_product(product_key)

        if "expected_score" in p:
            assert result["score"] == p["expected_score"], (
                f"{product_key}: score={result['score']}, expected exactly {p['expected_score']}"
            )
        elif "expected_range" in p:
            lo, hi = p["expected_range"]
            assert lo <= result["score"] <= hi, (
                f"{product_key}: score={result['score']}, expected {lo}-{hi}"
            )

    def test_grade(self, product_key):
        p = GOLDEN_PRODUCTS[product_key]
        result = _score_product(product_key)

        if "expected_grade" in p:
            assert result["grade"] == p["expected_grade"], (
                f"{product_key}: grade={result['grade']}, expected {p['expected_grade']}"
            )
        if "not_grade" in p:
            assert result["grade"] != p["not_grade"], (
                f"{product_key}: grade should not be {p['not_grade']}"
            )

    def test_result_structure(self, product_key):
        result = _score_product(product_key)
        for key in ("score", "grade", "reasons", "penalties",
                     "uncertainties", "personalized_conflicts",
                     "nutrition_used", "nutrition_confidence",
                     "beverage_label", "beverage_reason"):
            assert key in result, f"{product_key}: missing key '{key}'"


# ── Beverage detection ─────────────────────────────────────────────────────

class TestBeverageDetection:
    def test_cola_by_category(self):
        is_bev, reason = _is_beverage(categories=["sodas", "beverages"])
        assert is_bev is True

    def test_carbonated_drinks_category(self):
        is_bev, reason = _is_beverage(categories=["carbonated drinks"])
        assert is_bev is True

    def test_sparkling_water_by_category(self):
        is_bev, reason = _is_beverage(categories=["waters", "mineral waters"])
        assert is_bev is True

    def test_bread_not_beverage(self):
        is_bev, _ = _is_beverage(categories=["bread", "whole wheat bread"])
        assert is_bev is False

    def test_cereal_not_beverage(self):
        is_bev, _ = _is_beverage(categories=["breakfast cereals", "cereals"])
        assert is_bev is False


# ── Nutrition confidence ────────────────────────────────────────────────────

class TestNutritionConfidence:
    def test_high_when_nutrition_present(self):
        result = _score_product("cola_soda_like")
        assert result["nutrition_confidence"] == "high"

    def test_low_when_nutrition_missing(self):
        result = calculate_product_score(
            ingredients=["wheat flour", "water", "salt"],
        )
        assert result["nutrition_confidence"] == "low"


# ── UPF penalties ──────────────────────────────────────────────────────────

class TestUPFPenalties:
    def test_cola_has_upf_penalties(self):
        result = _score_product("cola_soda_like")
        upf_penalties = [p for p in result["penalties"] if "UPF" in p]
        assert len(upf_penalties) > 0, "Cola should have UPF penalty lines"

    def test_sparkling_water_no_upf(self):
        result = _score_product("sparkling_water")
        upf_penalties = [p for p in result["penalties"] if "UPF" in p]
        assert len(upf_penalties) == 0

    def test_upf_cap_with_nutrition(self):
        """UPF penalty capped at 15 when nutrition is present."""
        result = calculate_product_score(
            ingredients=[
                "sugar", "modified food starch", "caramel color",
                "artificial flavor", "soy lecithin", "maltodextrin",
                "sodium benzoate", "red 40", "aspartame",
                "hydrogenated oil",
            ],
            nutrition={
                "energy_kcal_100g": 100,
                "sugars_g_100g": 2,
                "sat_fat_g_100g": 0.5,
                "sodium_mg_100g": 50,
                "fiber_g_100g": 0,
                "protein_g_100g": 0,
            },
        )
        # With nutrition: UPF cap=15. Score should be 100 - 10(sugar) - 15(upf) = 75
        # (sugar 2g → pen 10, no other nutrition penalties hit)
        assert result["score"] >= 70, (
            f"Score {result['score']} – upf cap should limit penalty"
        )


# ── Position weight function ──────────────────────────────────────────────

class TestPositionWeight:
    def test_first_quintile(self):
        assert position_weight(0, 10) == 1.0
        assert position_weight(1, 10) == 1.0

    def test_middle(self):
        assert position_weight(3, 10) == 0.7

    def test_last(self):
        assert position_weight(9, 10) == 0.4

    def test_single_item(self):
        assert position_weight(0, 1) == 1.0


# ── Allergy hard fail ─────────────────────────────────────────────────────

class TestAllergyHardFail:
    def test_milk_allergy_score_zero(self):
        result = _score_product("allergy_hard_fail_milk")
        assert result["score"] == 0
        assert result["grade"] == "F"
        assert len(result["personalized_conflicts"]) > 0

    def test_peanut_allergy_score_zero(self):
        result = calculate_product_score(
            ingredients=["peanuts", "salt"],
            user_profile={"allergies": ["peanut"]},
        )
        assert result["score"] == 0


# ── Avoid terms ───────────────────────────────────────────────────────────

class TestAvoidTerms:
    def test_avoid_term_snake_case(self):
        result = calculate_product_score(
            ingredients=["wheat flour", "sugar", "palm oil"],
            user_profile={"avoid_terms": ["palm oil"]},
        )
        assert any("palm oil" in c.lower() for c in result["personalized_conflicts"])

    def test_avoid_term_camel_case(self):
        result = calculate_product_score(
            ingredients=["wheat flour", "sugar", "palm oil"],
            user_profile={"avoidTerms": ["palm oil"]},
        )
        assert any("palm oil" in c.lower() for c in result["personalized_conflicts"])


# ── Ingredient-only fallback ──────────────────────────────────────────────

class TestIngredientFallback:
    def test_clean_ingredients_capped(self):
        result = calculate_product_score(
            ingredients=["whole wheat flour", "water", "salt", "yeast"],
        )
        # Without nutrition, score is capped at 70
        assert result["score"] <= 70
        assert result["score"] >= 60
        assert result["nutrition_confidence"] == "low"
        assert result["nutrition_used"] is False

    def test_junk_ingredients_low_score(self):
        result = calculate_product_score(
            ingredients=["sugar", "high fructose corn syrup", "hydrogenated soybean oil",
                         "artificial flavor", "red 40", "yellow 5", "sodium benzoate"],
        )
        # Sugar proxy (−25) + UPF penalties (capped at 25 w/o nutrition)
        assert result["score"] <= 70

    def test_top3_sugar_proxy(self):
        with_sugar = calculate_product_score(
            ingredients=["sugar", "wheat flour", "palm oil"],
        )
        # Sugar proxy penalty should be present
        assert any("sugar proxy" in p.lower() for p in with_sugar["penalties"])
        # Score should be reduced below the cap
        assert with_sugar["score"] <= 70


# ── Edge cases ────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_inputs(self):
        result = calculate_product_score(ingredients=[])
        assert result["score"] == 50
        assert result["grade"] == "C"
        assert result["nutrition_confidence"] == "low"

    def test_score_clamped_zero(self):
        result = calculate_product_score(
            ingredients=["sugar", "corn syrup", "hydrogenated oil",
                         "red 40", "yellow 5", "sodium nitrite",
                         "artificial flavor", "modified starch",
                         "palm oil", "sodium benzoate"],
        )
        assert result["score"] >= 0

    def test_result_structure(self):
        result = calculate_product_score(
            ingredients=["water", "salt"],
        )
        for key in ("score", "grade", "reasons", "penalties",
                     "uncertainties", "personalized_conflicts",
                     "nutrition_used", "nutrition_confidence",
                     "beverage_label", "beverage_reason"):
            assert key in result
