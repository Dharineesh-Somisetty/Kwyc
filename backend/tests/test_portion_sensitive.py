"""Tests for portion-sensitive scoring and dual view (per-100g vs per-serving).

Covers:
  1. Honey → portion_sensitive=True, primary_nutrition_view="serving"
  2. Lunchables-like meal → portion_sensitive=False, primary view "100g"
  3. Plain mixed nuts → portion_sensitive=True, default serving view
  4. Dual score computation: both nutrition_score_100g and nutrition_score_serving
  5. detect_portion_sensitive helper
"""

import pytest
from app.services.scorer import (
    calculate_product_score,
    detect_portion_sensitive,
)


# ---------------------------------------------------------------------------
# Test 1: Honey
# ---------------------------------------------------------------------------
class TestHoneyPortionSensitive:

    def _honey_result(self):
        return calculate_product_score(
            ingredients=["honey"],
            nutrition={
                "energy_kcal_100g": 304,
                "sugars_g_100g": 82.0,
                "sat_fat_g_100g": 0.0,
                "sodium_mg_100g": 4.0,
                "fiber_g_100g": 0.0,
                "protein_g_100g": 0.3,
            },
            nutrition_per_serving={
                "serving_size_text": "1 Tbsp (21g)",
                "serving_size_value": 21.0,
                "serving_size_unit": "g",
                "calories": 64,
                "total_sugars_g": 17.0,
                "added_sugars_g": 17.0,
                "saturated_fat_g": 0.0,
                "sodium_mg": 1.0,
                "fiber_g": 0.0,
                "protein_g": 0.1,
            },
            product_name="Pure Honey",
        )

    def test_honey_portion_sensitive(self):
        result = self._honey_result()
        pi = result["portion_info"]
        assert pi["portion_sensitive"] is True

    def test_honey_primary_view_serving(self):
        result = self._honey_result()
        assert result["primary_nutrition_view"] == "serving"

    def test_honey_has_100g_score(self):
        result = self._honey_result()
        ns100 = result["nutrition_score_100g"]
        assert ns100 is not None
        assert ns100["basis"] == "100g"
        assert isinstance(ns100["score"], int)

    def test_honey_has_serving_score(self):
        result = self._honey_result()
        ns_srv = result["nutrition_score_serving"]
        assert ns_srv is not None
        assert ns_srv["basis"] == "serving"
        assert isinstance(ns_srv["score"], int)

    def test_honey_serving_score_higher_than_100g(self):
        """Per-serving should be less extreme than per-100g for sugar-dense items."""
        result = self._honey_result()
        ns100 = result["nutrition_score_100g"]
        ns_srv = result["nutrition_score_serving"]
        # Serving score should be higher (= less extreme penalties) for honey
        assert ns_srv["score"] > ns100["score"]

    def test_honey_note(self):
        result = self._honey_result()
        pi = result["portion_info"]
        assert pi["note"] is not None
        assert "small amounts" in pi["note"].lower() or "sugar density" in pi["note"].lower()


# ---------------------------------------------------------------------------
# Test 2: Lunchables-like meal (NOT portion sensitive)
# ---------------------------------------------------------------------------
class TestLunchablesNotPortionSensitive:

    def _lunchables_result(self):
        return calculate_product_score(
            ingredients=[
                "enriched flour", "water", "mozzarella cheese", "tomato paste",
                "sugar", "modified corn starch", "soybean oil", "salt",
                "natural flavor", "sodium benzoate",
            ],
            nutrition={
                "energy_kcal_100g": 250,
                "sugars_g_100g": 8.0,
                "sat_fat_g_100g": 6.0,
                "sodium_mg_100g": 650.0,
                "fiber_g_100g": 1.0,
                "protein_g_100g": 8.0,
            },
            nutrition_per_serving={
                "serving_size_text": "1 package (128g)",
                "serving_size_value": 128.0,
                "serving_size_unit": "g",
                "calories": 320,
                "total_sugars_g": 10.0,
                "added_sugars_g": 6.0,
                "saturated_fat_g": 8.0,
                "sodium_mg": 830.0,
                "fiber_g": 1.0,
                "protein_g": 10.0,
            },
            product_name="Lunchables Pizza",
        )

    def test_lunchables_not_portion_sensitive(self):
        result = self._lunchables_result()
        pi = result["portion_info"]
        assert pi["portion_sensitive"] is False

    def test_lunchables_primary_view_100g(self):
        result = self._lunchables_result()
        assert result["primary_nutrition_view"] == "100g"

    def test_lunchables_has_both_scores(self):
        result = self._lunchables_result()
        assert result["nutrition_score_100g"] is not None
        assert result["nutrition_score_serving"] is not None


# ---------------------------------------------------------------------------
# Test 3: Plain mixed nuts
# ---------------------------------------------------------------------------
class TestPlainNutsPortionSensitive:

    def _nuts_result(self):
        return calculate_product_score(
            ingredients=["almonds", "cashews", "pecans", "sea salt"],
            nutrition={
                "energy_kcal_100g": 607,
                "sugars_g_100g": 4.0,
                "sat_fat_g_100g": 5.5,
                "sodium_mg_100g": 260.0,
                "fiber_g_100g": 7.0,
                "protein_g_100g": 18.0,
            },
            nutrition_per_serving={
                "serving_size_text": "1 oz (28g)",
                "serving_size_value": 28.0,
                "serving_size_unit": "g",
                "calories": 170,
                "total_sugars_g": 1.0,
                "added_sugars_g": 0.0,
                "saturated_fat_g": 1.5,
                "sodium_mg": 75.0,
                "fiber_g": 2.0,
                "protein_g": 5.0,
            },
            product_name="Mixed Nuts",
        )

    def test_nuts_portion_sensitive(self):
        result = self._nuts_result()
        pi = result["portion_info"]
        assert pi["portion_sensitive"] is True

    def test_nuts_primary_view_serving(self):
        result = self._nuts_result()
        assert result["primary_nutrition_view"] == "serving"

    def test_nuts_category(self):
        result = self._nuts_result()
        assert result["category"] == "nuts_seeds_plain"

    def test_nuts_has_both_scores(self):
        result = self._nuts_result()
        assert result["nutrition_score_100g"] is not None
        assert result["nutrition_score_serving"] is not None

    def test_nuts_note(self):
        result = self._nuts_result()
        pi = result["portion_info"]
        assert pi["note"] is not None
        assert "portion" in pi["note"].lower()


# ---------------------------------------------------------------------------
# Test 4: detect_portion_sensitive helper directly
# ---------------------------------------------------------------------------
class TestDetectPortionSensitiveHelper:

    def test_honey_ingredients(self):
        info = detect_portion_sensitive(
            ["honey"],
            is_honey_syrup=True,
        )
        assert info["portion_sensitive"] is True
        assert "sugar density" in info["note"].lower() or "small amounts" in info["note"].lower()

    def test_olive_oil(self):
        info = detect_portion_sensitive(
            ["extra virgin olive oil"],
            is_plain_oil=True,
        )
        assert info["portion_sensitive"] is True
        assert "calorie dense" in info["note"].lower()

    def test_peanut_butter(self):
        info = detect_portion_sensitive(
            ["peanuts", "salt"],
            product_name="Peanut Butter",
        )
        assert info["portion_sensitive"] is True

    def test_small_serving_size(self):
        info = detect_portion_sensitive(
            ["tomato", "water", "salt"],
            nutrition_per_serving={
                "serving_size_value": 15.0,
                "serving_size_unit": "g",
                "serving_size_text": "1 Tbsp (15g)",
            },
        )
        assert info["portion_sensitive"] is True
        assert info["typical_serving_text"] == "1 Tbsp (15g)"

    def test_regular_product_not_sensitive(self):
        info = detect_portion_sensitive(
            ["enriched flour", "water", "sugar", "soybean oil", "salt"],
            nutrition_per_serving={
                "serving_size_value": 50.0,
                "serving_size_unit": "g",
            },
        )
        assert info["portion_sensitive"] is False

    def test_product_name_fallback_honey(self):
        info = detect_portion_sensitive(
            [],
            product_name="Raw Honey",
        )
        assert info["portion_sensitive"] is True


# ---------------------------------------------------------------------------
# Test 5: Dual score structure
# ---------------------------------------------------------------------------
class TestDualScoreStructure:

    def test_only_per100g_data(self):
        """When only per-100g data is available, serving score should be None."""
        result = calculate_product_score(
            ingredients=["sugar", "corn syrup", "water"],
            nutrition={
                "energy_kcal_100g": 300,
                "sugars_g_100g": 70.0,
                "sat_fat_g_100g": 0.0,
                "sodium_mg_100g": 20.0,
            },
        )
        assert result["nutrition_score_100g"] is not None
        assert result["nutrition_score_serving"] is None
        assert result["primary_nutrition_view"] == "100g"

    def test_only_per_serving_data(self):
        """When only per-serving data, 100g score should be None."""
        result = calculate_product_score(
            ingredients=["oats", "sugar", "vegetable oil"],
            nutrition_per_serving={
                "calories": 120,
                "sodium_mg": 150,
                "saturated_fat_g": 2.0,
                "total_sugars_g": 8.0,
            },
        )
        assert result["nutrition_score_100g"] is None
        assert result["nutrition_score_serving"] is not None
        assert result["primary_nutrition_view"] in ("100g", "serving")

    def test_portion_info_always_present(self):
        """portion_info should always be in the result."""
        result = calculate_product_score(
            ingredients=["water", "sugar"],
        )
        assert "portion_info" in result
        assert isinstance(result["portion_info"], dict)

    def test_no_data_defaults(self):
        """With no data at all, portion_info should be safe defaults."""
        result = calculate_product_score()
        assert result["portion_info"]["portion_sensitive"] is False
        assert result["primary_nutrition_view"] == "100g"
