"""Tests for category-aware scoring of plain nuts/seeds.

Verifies that:
- Plain mixed nuts (unsalted, no added sugars) score >= 65 (prefer >= 75).
- Sugary/candied nuts score much lower.
- Salted nuts (high sodium) score lower.
- Allergens do NOT penalize base health score unless user_profile has a
  matching allergy.
- The _is_plain_nuts_seeds detector correctly classifies edge cases.
"""

import pytest
from app.services.scorer import (
    calculate_product_score,
    _is_plain_nuts_seeds,
    _normalize,
)


# ── Realistic nutrition profiles ──────────────────────────────────────────

PLAIN_MIXED_NUTS_NUT_100G = {
    "energy_kcal_100g": 607,
    "sugars_g_100g": 4.2,
    "sat_fat_g_100g": 6.5,
    "sodium_mg_100g": 3,
    "fiber_g_100g": 7.9,
    "protein_g_100g": 20.0,
}

PLAIN_ALMONDS_NUT_100G = {
    "energy_kcal_100g": 579,
    "sugars_g_100g": 3.9,
    "sat_fat_g_100g": 3.7,
    "sodium_mg_100g": 1,
    "fiber_g_100g": 12.5,
    "protein_g_100g": 21.2,
}

CANDIED_NUTS_NUT_100G = {
    "energy_kcal_100g": 520,
    "sugars_g_100g": 28.0,
    "sat_fat_g_100g": 5.0,
    "sodium_mg_100g": 150,
    "fiber_g_100g": 4.0,
    "protein_g_100g": 12.0,
}

SALTED_NUTS_NUT_100G = {
    "energy_kcal_100g": 607,
    "sugars_g_100g": 4.2,
    "sat_fat_g_100g": 6.5,
    "sodium_mg_100g": 600,      # heavily salted
    "fiber_g_100g": 7.9,
    "protein_g_100g": 20.0,
}

HONEY_ROASTED_NUTS_NUT_100G = {
    "energy_kcal_100g": 560,
    "sugars_g_100g": 18.0,
    "sat_fat_g_100g": 5.5,
    "sodium_mg_100g": 200,
    "fiber_g_100g": 5.0,
    "protein_g_100g": 16.0,
}


# ── Category detector unit tests ──────────────────────────────────────────

class TestIsPlainNutsSeeds:
    def test_plain_mixed_nuts(self):
        assert _is_plain_nuts_seeds(
            ["cashews", "almonds", "pecans", "brazil nuts"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
        ) is True

    def test_plain_almonds_with_oil_salt(self):
        assert _is_plain_nuts_seeds(
            ["almonds", "peanut oil", "sea salt"],
            nutrition=PLAIN_ALMONDS_NUT_100G,
        ) is True

    def test_candied_nuts_disqualified(self):
        assert _is_plain_nuts_seeds(
            ["peanuts", "sugar", "corn syrup", "salt"],
            nutrition=CANDIED_NUTS_NUT_100G,
        ) is False

    def test_honey_roasted_disqualified(self):
        assert _is_plain_nuts_seeds(
            ["almonds", "honey", "salt"],
            nutrition=HONEY_ROASTED_NUTS_NUT_100G,
        ) is False

    def test_high_sodium_disqualified(self):
        assert _is_plain_nuts_seeds(
            ["cashews", "almonds", "salt"],
            nutrition=SALTED_NUTS_NUT_100G,
        ) is False

    def test_upf_flavored_disqualified(self):
        assert _is_plain_nuts_seeds(
            ["peanuts", "natural flavors", "salt"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
        ) is False

    def test_non_nut_product_returns_false(self):
        assert _is_plain_nuts_seeds(
            ["wheat flour", "water", "salt", "yeast"],
        ) is False

    def test_empty_ingredients_false(self):
        assert _is_plain_nuts_seeds([]) is False

    def test_mixed_with_chocolate_disqualified(self):
        assert _is_plain_nuts_seeds(
            ["peanuts", "almonds", "chocolate", "sugar"],
            nutrition=CANDIED_NUTS_NUT_100G,
        ) is False

    def test_per_serving_added_sugars_disqualifies(self):
        """Added sugars > 0 from per-serving data disqualifies."""
        assert _is_plain_nuts_seeds(
            ["cashews", "almonds", "pecans"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
            nutrition_per_serving={"added_sugars_g": 3.0},
        ) is False

    def test_per_serving_high_sodium_disqualifies(self):
        """Sodium > 120 mg/serving disqualifies."""
        assert _is_plain_nuts_seeds(
            ["cashews", "almonds", "pecans"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
            nutrition_per_serving={"sodium_mg": 200},
        ) is False

    def test_dry_roasted_no_salt(self):
        """Dry roasted with no salt still qualifies."""
        assert _is_plain_nuts_seeds(
            ["dry roasted almonds"],
            nutrition=PLAIN_ALMONDS_NUT_100G,
        ) is True


# ── Scoring tests ─────────────────────────────────────────────────────────

class TestPlainNutsScoring:
    """Plain mixed nuts should score >= 65 (prefer >= 75)."""

    def test_plain_mixed_nuts_score_high(self):
        result = calculate_product_score(
            ingredients=["cashews", "almonds", "pecans", "brazil nuts"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
            product_name="Mixed Nuts",
        )
        assert result["score"] >= 65, (
            f"Plain mixed nuts should score >= 65, got {result['score']}"
        )

    def test_plain_mixed_nuts_prefer_75(self):
        result = calculate_product_score(
            ingredients=["cashews", "almonds", "pecans", "brazil nuts"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
            product_name="Mixed Nuts",
        )
        assert result["score"] >= 75, (
            f"Plain mixed nuts should ideally score >= 75, got {result['score']}"
        )

    def test_plain_almonds_score_high(self):
        result = calculate_product_score(
            ingredients=["almonds"],
            nutrition=PLAIN_ALMONDS_NUT_100G,
            product_name="Almonds",
        )
        assert result["score"] >= 75, (
            f"Plain almonds should score >= 75, got {result['score']}"
        )

    def test_plain_nuts_has_whole_food_reason(self):
        result = calculate_product_score(
            ingredients=["cashews", "almonds", "pecans"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
            product_name="Mixed Nuts",
        )
        assert any(
            "minimally processed nuts" in r.lower() for r in result["reasons"]
        ), "Should contain 'minimally processed nuts' reason"

    def test_plain_nuts_does_not_exceed_100(self):
        result = calculate_product_score(
            ingredients=["almonds"],
            nutrition=PLAIN_ALMONDS_NUT_100G,
            product_name="Almonds",
        )
        assert result["score"] <= 100


class TestCandiedNutsScoring:
    """Sugary/candied nuts should score much lower than plain."""

    def test_candied_nuts_score_lower(self):
        plain = calculate_product_score(
            ingredients=["cashews", "almonds", "pecans", "brazil nuts"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
            product_name="Mixed Nuts",
        )
        candied = calculate_product_score(
            ingredients=["peanuts", "sugar", "corn syrup", "salt"],
            nutrition=CANDIED_NUTS_NUT_100G,
            product_name="Candied Peanuts",
        )
        assert candied["score"] < plain["score"] - 20, (
            f"Candied nuts ({candied['score']}) should be >> lower than "
            f"plain ({plain['score']})"
        )

    def test_candied_nuts_below_55(self):
        result = calculate_product_score(
            ingredients=["peanuts", "sugar", "corn syrup", "salt"],
            nutrition=CANDIED_NUTS_NUT_100G,
            product_name="Candied Peanuts",
        )
        assert result["score"] <= 55, (
            f"Candied nuts should score <= 55, got {result['score']}"
        )

    def test_honey_roasted_not_plain(self):
        result = calculate_product_score(
            ingredients=["almonds", "honey", "salt", "modified food starch"],
            nutrition=HONEY_ROASTED_NUTS_NUT_100G,
            product_name="Honey Roasted Almonds",
        )
        assert not any(
            "minimally processed nuts" in r.lower() for r in result["reasons"]
        ), "Honey roasted should NOT get whole-food credit"


class TestSaltedNutsScoring:
    """Heavily salted nuts should score lower than plain unsalted."""

    def test_salted_nuts_lower_than_unsalted(self):
        unsalted = calculate_product_score(
            ingredients=["cashews", "almonds", "pecans"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
            product_name="Unsalted Mixed Nuts",
        )
        salted = calculate_product_score(
            ingredients=["cashews", "almonds", "pecans", "salt"],
            nutrition=SALTED_NUTS_NUT_100G,
            product_name="Salted Mixed Nuts",
        )
        assert salted["score"] < unsalted["score"], (
            f"Salted ({salted['score']}) should score lower than "
            f"unsalted ({unsalted['score']})"
        )

    def test_heavily_salted_loses_nuts_benefit(self):
        """Nuts with > 480 mg sodium/100g should not get plain-nuts treatment."""
        result = calculate_product_score(
            ingredients=["cashews", "almonds", "pecans", "salt"],
            nutrition=SALTED_NUTS_NUT_100G,
            product_name="Heavily Salted Nuts",
        )
        assert not any(
            "minimally processed nuts" in r.lower() for r in result["reasons"]
        ), "Heavily salted nuts should NOT get whole-food credit"


# ── Allergen handling ─────────────────────────────────────────────────────

class TestAllergenNotInBaseScore:
    """Allergens should NOT penalize the base health score unless
    user_profile actually has that allergy."""

    def test_nut_allergen_no_penalty_without_allergy(self):
        """Peanuts scored without any user allergy should not be penalized
        for being an allergen in the base score."""
        no_allergy = calculate_product_score(
            ingredients=["peanuts", "salt"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
            product_name="Peanuts",
        )
        assert no_allergy["personalized_conflicts"] == []
        assert no_allergy["score"] > 0

    def test_nut_allergen_zero_when_user_allergic(self):
        result = calculate_product_score(
            ingredients=["peanuts", "salt"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
            product_name="Peanuts",
            user_profile={"allergies": ["peanut"]},
        )
        assert result["score"] == 0
        assert result["grade"] == "F"
        assert len(result["personalized_conflicts"]) > 0

    def test_tree_nut_allergy_only_in_personalized(self):
        """Tree nut allergy shows in personalized_conflicts, not base score."""
        without_allergy = calculate_product_score(
            ingredients=["almonds", "cashews"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
            product_name="Mixed Nuts",
        )
        with_allergy = calculate_product_score(
            ingredients=["almonds", "cashews"],
            nutrition=PLAIN_MIXED_NUTS_NUT_100G,
            product_name="Mixed Nuts",
            user_profile={"allergies": ["almond"]},
        )
        # Without allergy, base score should be decent
        assert without_allergy["score"] >= 65
        assert without_allergy["personalized_conflicts"] == []
        # With allergy, score drops to 0
        assert with_allergy["score"] == 0


# ── Edge cases ────────────────────────────────────────────────────────────

class TestNutsEdgeCases:
    def test_single_nut_ingredient(self):
        """A product that is literally just almonds."""
        result = calculate_product_score(
            ingredients=["almonds"],
            nutrition=PLAIN_ALMONDS_NUT_100G,
            product_name="Almonds",
        )
        assert result["score"] >= 75

    def test_nuts_with_per_serving_only(self):
        """Per-serving scoring path with plain nuts."""
        per_serving = {
            "calories": 170,
            "total_fat_g": 14,
            "saturated_fat_g": 2.0,
            "sodium_mg": 0,
            "total_sugars_g": 1.0,
            "added_sugars_g": 0,
            "fiber_g": 3.0,
            "protein_g": 6.0,
        }
        result = calculate_product_score(
            ingredients=["cashews", "almonds", "pecans"],
            nutrition_per_serving=per_serving,
            product_name="Mixed Nuts",
        )
        assert result["score"] >= 65, (
            f"Nuts with per-serving data should score >= 65, got {result['score']}"
        )

    def test_trail_mix_with_sugar_does_not_qualify(self):
        """Trail mix with candy/chocolate does not get plain-nuts treatment."""
        result = calculate_product_score(
            ingredients=["peanuts", "raisins", "chocolate", "sugar", "sunflower seeds"],
            nutrition={
                "energy_kcal_100g": 480,
                "sugars_g_100g": 22.0,
                "sat_fat_g_100g": 4.5,
                "sodium_mg_100g": 80,
                "fiber_g_100g": 4.0,
                "protein_g_100g": 12.0,
            },
            product_name="Trail Mix",
        )
        assert not any(
            "minimally processed nuts" in r.lower() for r in result["reasons"]
        )
