"""Tests for category-aware scoring, processing badges, and ingredient inference.

Covers:
- Plain nuts: wellness score >= 70, processing_badge = minimally_processed
- Honey: low wellness score (sugar-dense), processing_badge = minimally_processed
- Plain oils: decent score with energy adjustment, minimally_processed badge
- Lunchables-style: low wellness score, upf_signals badge
- Split outputs (nutrition_score, processing_badge) always present
- Ingredient inference fallback when OCR fails
"""

import pytest
from app.services.scorer import (
    calculate_product_score,
    _is_plain_nuts_seeds,
    _is_honey_syrup,
    _is_plain_oil,
    _compute_processing_badge,
    _try_infer_ingredients,
)


# ── Nutrition profiles ────────────────────────────────────────────────────

PLAIN_MIXED_NUTS_NUT = {
    "energy_kcal_100g": 607,
    "sugars_g_100g": 4.2,
    "sat_fat_g_100g": 6.5,
    "sodium_mg_100g": 3,
    "fiber_g_100g": 7.9,
    "protein_g_100g": 20.0,
}

HONEY_NUT = {
    "energy_kcal_100g": 304,
    "sugars_g_100g": 82.0,
    "sat_fat_g_100g": 0.0,
    "sodium_mg_100g": 4,
    "fiber_g_100g": 0.2,
    "protein_g_100g": 0.3,
}

OLIVE_OIL_NUT = {
    "energy_kcal_100g": 884,
    "sugars_g_100g": 0.0,
    "sat_fat_g_100g": 14.0,
    "sodium_mg_100g": 2,
    "fiber_g_100g": 0.0,
    "protein_g_100g": 0.0,
}

LUNCHABLES_NUT = {
    "energy_kcal_100g": 280,
    "sugars_g_100g": 15.0,
    "sat_fat_g_100g": 8.0,
    "sodium_mg_100g": 900,
    "fiber_g_100g": 1.0,
    "protein_g_100g": 10.0,
}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Plain nuts: score >= 70, minimally_processed
# ═══════════════════════════════════════════════════════════════════════════

class TestPlainNutsScoring:
    def test_plain_nuts_score_ge_70(self):
        result = calculate_product_score(
            ingredients=["cashews", "almonds", "pecans", "brazil nuts"],
            nutrition=PLAIN_MIXED_NUTS_NUT,
            product_name="Mixed Nuts",
        )
        assert result["score"] >= 70, (
            f"Plain nuts should score >= 70, got {result['score']}"
        )
        assert result["grade"] != "F"

    def test_plain_nuts_not_grade_f(self):
        result = calculate_product_score(
            ingredients=["almonds"],
            nutrition=PLAIN_MIXED_NUTS_NUT,
            product_name="Almonds",
        )
        assert result["grade"] != "F", (
            f"Plain nuts should never be F, got grade={result['grade']} score={result['score']}"
        )

    def test_plain_nuts_processing_badge_minimal(self):
        result = calculate_product_score(
            ingredients=["cashews", "almonds", "pecans"],
            nutrition=PLAIN_MIXED_NUTS_NUT,
            product_name="Mixed Nuts",
        )
        badge = result["processing_badge"]
        assert badge["level"] == "minimally_processed"
        assert badge["signals"] == []

    def test_plain_nuts_category_detected(self):
        result = calculate_product_score(
            ingredients=["cashews", "almonds", "pecans"],
            nutrition=PLAIN_MIXED_NUTS_NUT,
            product_name="Mixed Nuts",
        )
        assert result["category"] == "nuts_seeds_plain"

    def test_split_outputs_present_nuts(self):
        result = calculate_product_score(
            ingredients=["cashews", "almonds"],
            nutrition=PLAIN_MIXED_NUTS_NUT,
            product_name="Mixed Nuts",
        )
        assert "nutrition_score" in result
        assert "processing_badge" in result
        # top-level score is final_score = round(0.7 * nutrition + 0.3 * processing)
        expected = round(0.7 * result["nutrition_score"]["score"] + 0.3 * result["processing"]["processing_score"])
        assert result["score"] == expected


# ═══════════════════════════════════════════════════════════════════════════
# 2. Honey: low wellness, but minimally_processed badge
# ═══════════════════════════════════════════════════════════════════════════

class TestHoneyScoring:
    def test_honey_wellness_low(self):
        """Pure honey should have a low wellness score (very high sugar)."""
        result = calculate_product_score(
            ingredients=["honey"],
            nutrition=HONEY_NUT,
            product_name="Raw Honey",
        )
        # 82g sugar/100g → heavy penalty; score should be low
        assert result["score"] < 50, (
            f"Honey wellness score should be low, got {result['score']}"
        )

    def test_honey_processing_badge_minimal(self):
        """Pure honey is minimally processed even though nutrition score is low."""
        result = calculate_product_score(
            ingredients=["honey"],
            nutrition=HONEY_NUT,
            product_name="Raw Honey",
        )
        badge = result["processing_badge"]
        assert badge["level"] == "minimally_processed", (
            f"Honey should be minimally_processed, got {badge['level']}"
        )

    def test_honey_category_detected(self):
        result = calculate_product_score(
            ingredients=["honey"],
            nutrition=HONEY_NUT,
            product_name="Raw Honey",
        )
        assert result["category"] == "honey_syrup"

    def test_honey_no_upf_penalty(self):
        """Honey should NOT have UPF processing penalties."""
        result = calculate_product_score(
            ingredients=["honey"],
            nutrition=HONEY_NUT,
            product_name="Raw Honey",
        )
        upf_penalties = [p for p in result["penalties"] if "UPF" in p]
        assert len(upf_penalties) == 0, (
            f"Honey should have no UPF penalties, got {upf_penalties}"
        )

    def test_maple_syrup_also_detected(self):
        result = calculate_product_score(
            ingredients=["pure maple syrup"],
            nutrition=HONEY_NUT,
            product_name="Maple Syrup",
        )
        assert result["category"] == "honey_syrup"
        assert result["processing_badge"]["level"] == "minimally_processed"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Plain oils: adjusted score, minimally_processed
# ═══════════════════════════════════════════════════════════════════════════

class TestPlainOilScoring:
    def test_olive_oil_processing_badge_minimal(self):
        result = calculate_product_score(
            ingredients=["extra virgin olive oil"],
            nutrition=OLIVE_OIL_NUT,
            product_name="Olive Oil",
        )
        badge = result["processing_badge"]
        assert badge["level"] == "minimally_processed"

    def test_olive_oil_category_detected(self):
        result = calculate_product_score(
            ingredients=["extra virgin olive oil"],
            nutrition=OLIVE_OIL_NUT,
            product_name="Olive Oil",
        )
        assert result["category"] == "oils_plain"

    def test_olive_oil_no_upf_penalty(self):
        result = calculate_product_score(
            ingredients=["extra virgin olive oil"],
            nutrition=OLIVE_OIL_NUT,
            product_name="Olive Oil",
        )
        upf_penalties = [p for p in result["penalties"] if "UPF" in p]
        assert len(upf_penalties) == 0

    def test_olive_oil_has_portion_note(self):
        result = calculate_product_score(
            ingredients=["extra virgin olive oil"],
            nutrition=OLIVE_OIL_NUT,
            product_name="Olive Oil",
        )
        assert any("portion matters" in r.lower() for r in result["reasons"])

    def test_oil_with_additives_not_plain(self):
        """Oil + artificial flavor should not be categorized as plain oil."""
        result = calculate_product_score(
            ingredients=["olive oil", "artificial flavor", "garlic extract"],
            nutrition=OLIVE_OIL_NUT,
            product_name="Flavored Olive Oil",
        )
        assert result["category"] != "oils_plain"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Lunchables-like: low wellness, upf_signals badge
# ═══════════════════════════════════════════════════════════════════════════

class TestLunchablesScoring:
    def test_lunchables_low_score(self):
        result = calculate_product_score(
            ingredients=[
                "enriched flour", "sugar", "modified food starch",
                "sodium benzoate", "artificial flavor", "yellow 5",
                "soy lecithin", "palm oil", "salt",
            ],
            nutrition=LUNCHABLES_NUT,
            product_name="Lunchables",
        )
        assert result["score"] < 50, (
            f"Lunchables should score < 50, got {result['score']}"
        )

    def test_lunchables_upf_signals_badge(self):
        result = calculate_product_score(
            ingredients=[
                "enriched flour", "sugar", "modified food starch",
                "sodium benzoate", "artificial flavor", "yellow 5",
                "soy lecithin", "palm oil", "salt",
            ],
            nutrition=LUNCHABLES_NUT,
            product_name="Lunchables",
        )
        badge = result["processing_badge"]
        assert badge["level"] == "upf_signals", (
            f"Lunchables should have upf_signals badge, got {badge['level']}"
        )
        assert len(badge["signals"]) > 0

    def test_lunchables_not_minimally_processed(self):
        result = calculate_product_score(
            ingredients=[
                "enriched flour", "sugar", "modified food starch",
                "sodium benzoate", "artificial flavor",
            ],
            nutrition=LUNCHABLES_NUT,
            product_name="Lunchables",
        )
        assert result["processing_badge"]["level"] != "minimally_processed"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Split outputs always present
# ═══════════════════════════════════════════════════════════════════════════

class TestSplitOutputs:
    def test_split_outputs_keys(self):
        result = calculate_product_score(
            ingredients=["water", "salt"],
            nutrition={"energy_kcal_100g": 0, "sugars_g_100g": 0,
                       "sat_fat_g_100g": 0, "sodium_mg_100g": 100},
        )
        assert "nutrition_score" in result
        assert "processing_badge" in result
        assert "category" in result
        assert "ingredients_inferred" in result

    def test_nutrition_score_matches_top_level(self):
        result = calculate_product_score(
            ingredients=["water", "salt"],
            nutrition={"energy_kcal_100g": 0, "sugars_g_100g": 0,
                       "sat_fat_g_100g": 0, "sodium_mg_100g": 100},
        )
        # top-level score is final_score = round(0.7 * nutrition + 0.3 * processing)
        expected = round(0.7 * result["nutrition_score"]["score"] + 0.3 * result["processing"]["processing_score"])
        assert result["score"] == expected

    def test_processing_badge_has_level(self):
        result = calculate_product_score(
            ingredients=["water", "salt"],
        )
        badge = result["processing_badge"]
        assert badge["level"] in ("minimally_processed", "processed", "upf_signals")
        assert isinstance(badge["signals"], list)

    def test_two_ingredients_minimally_processed(self):
        """<= 2 ingredients with no UPF => minimally_processed."""
        result = calculate_product_score(
            ingredients=["water", "salt"],
        )
        assert result["processing_badge"]["level"] == "minimally_processed"


# ═══════════════════════════════════════════════════════════════════════════
# 6. Category detector unit tests
# ═══════════════════════════════════════════════════════════════════════════

class TestHoneySyrupDetector:
    def test_pure_honey(self):
        assert _is_honey_syrup(["honey"]) is True

    def test_raw_honey(self):
        assert _is_honey_syrup(["raw honey"]) is True

    def test_maple_syrup(self):
        assert _is_honey_syrup(["pure maple syrup"]) is True

    def test_honey_with_flavors_disqualified(self):
        assert _is_honey_syrup(["honey", "natural flavors"]) is False

    def test_non_honey(self):
        assert _is_honey_syrup(["sugar", "water"]) is False

    def test_empty(self):
        assert _is_honey_syrup([]) is False


class TestPlainOilDetector:
    def test_olive_oil(self):
        assert _is_plain_oil(["extra virgin olive oil"]) is True

    def test_avocado_oil(self):
        assert _is_plain_oil(["avocado oil"]) is True

    def test_coconut_oil(self):
        assert _is_plain_oil(["coconut oil"]) is True

    def test_oil_with_preservative_disqualified(self):
        assert _is_plain_oil(["olive oil", "bha", "tbhq"]) is False

    def test_too_many_ingredients_disqualified(self):
        assert _is_plain_oil(["olive oil", "garlic", "basil", "oregano"]) is False

    def test_non_oil(self):
        assert _is_plain_oil(["wheat flour"]) is False


class TestProcessingBadge:
    def test_no_upf_two_ingredients(self):
        badge = _compute_processing_badge(["water", "salt"])
        assert badge["level"] == "minimally_processed"
        assert badge["signals"] == []

    def test_upf_signals_detected(self):
        badge = _compute_processing_badge([
            "flour", "modified food starch", "artificial flavor",
        ])
        assert badge["level"] == "upf_signals"
        assert len(badge["signals"]) > 0

    def test_honey_overrides_to_minimal(self):
        badge = _compute_processing_badge(["honey"], is_honey_syrup=True)
        assert badge["level"] == "minimally_processed"

    def test_plain_nuts_minimal(self):
        badge = _compute_processing_badge(
            ["cashews", "almonds", "pecans"], is_plain_nuts=True,
        )
        assert badge["level"] == "minimally_processed"


# ═══════════════════════════════════════════════════════════════════════════
# 7. Ingredient inference fallback
# ═══════════════════════════════════════════════════════════════════════════

class TestIngredientInference:
    def test_infer_honey_from_name(self):
        ing, cat, did = _try_infer_ingredients("Raw Honey")
        assert did is True
        assert cat == "honey_syrup"
        assert ing is not None

    def test_infer_nuts_from_name(self):
        ing, cat, did = _try_infer_ingredients("Mixed Nuts")
        assert did is True
        assert cat == "nuts_seeds_plain"

    def test_infer_oil_from_name(self):
        ing, cat, did = _try_infer_ingredients("Extra Virgin Olive Oil")
        assert did is True
        assert cat == "oils_plain"

    def test_no_infer_generic_name(self):
        ing, cat, did = _try_infer_ingredients("Product XYZ")
        assert did is False

    def test_infer_from_category(self):
        ing, cat, did = _try_infer_ingredients(
            None, product_categories=["honey", "sweeteners"],
        )
        assert did is True
        assert cat == "honey_syrup"

    def test_scorer_uses_inferred_ingredients(self):
        """When ingredients are empty but product name implies honey,
        the scorer should infer and produce valid output."""
        result = calculate_product_score(
            ingredients=[],
            nutrition=HONEY_NUT,
            product_name="Raw Honey",
        )
        assert result["ingredients_inferred"] is True
        assert result["category"] == "honey_syrup"
        assert any("inferred" in u.lower() for u in result["uncertainties"])

    def test_no_inference_when_no_match(self):
        result = calculate_product_score(
            ingredients=[],
            nutrition=LUNCHABLES_NUT,
            product_name="Unknown Product",
        )
        # Should not infer — no name match
        assert result["ingredients_inferred"] is False


# ═══════════════════════════════════════════════════════════════════════════
# 8. Comparison: honey vs lunchables badges
# ═══════════════════════════════════════════════════════════════════════════

class TestBadgeComparison:
    def test_honey_vs_lunchables(self):
        """Honey and lunchables should have different processing badges
        even though honey may have a lower or equal wellness score."""
        honey_result = calculate_product_score(
            ingredients=["honey"],
            nutrition=HONEY_NUT,
            product_name="Raw Honey",
        )
        lunchables_result = calculate_product_score(
            ingredients=[
                "enriched flour", "sugar", "modified food starch",
                "sodium benzoate", "artificial flavor", "yellow 5",
            ],
            nutrition=LUNCHABLES_NUT,
            product_name="Lunchables",
        )
        assert honey_result["processing_badge"]["level"] == "minimally_processed"
        assert lunchables_result["processing_badge"]["level"] == "upf_signals"
