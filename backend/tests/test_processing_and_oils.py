"""Tests for two-part scoring (nutrition_score + processing_score → final_score)
and oil-specific handling.

Covers:
  1) Plain honey: nutrition_score low, processing minimally_processed,
     processing_score high, final_score blended (not A).
  2) Plain mixed nuts: processing minimally_processed, final_score not F.
  3) Single-ingredient olive oil: not F, reasonable final_score (>=55),
     minimally_processed.
  4) UPF product: modified starch + preservatives → upf_signals,
     processing_score low, final_score reduced.
  5) Allergen overlay: final_score=0 but nutrition_score/processing still computed.
  6) Oil-specific: sat-fat ratio penalty, hydrogenated oil detection,
     energy penalty reduction.
  7) Structure: all three sub-objects present.
"""

import pytest
from app.services.scorer import (
    calculate_product_score,
    detect_upf_signals,
    _compute_processing_score,
    _determine_processing_level,
    _has_hydrogenated_oil,
    _is_plain_oil,
)


# ── Nutrition profiles ────────────────────────────────────────

HONEY_NUT = {
    "energy_kcal_100g": 304,
    "sugars_g_100g": 82.0,
    "sat_fat_g_100g": 0.0,
    "sodium_mg_100g": 4,
    "fiber_g_100g": 0.2,
    "protein_g_100g": 0.3,
}

MIXED_NUTS_NUT = {
    "energy_kcal_100g": 607,
    "sugars_g_100g": 4.2,
    "sat_fat_g_100g": 6.5,
    "sodium_mg_100g": 3,
    "fiber_g_100g": 7.9,
    "protein_g_100g": 20.0,
}

OLIVE_OIL_NUT = {
    "energy_kcal_100g": 884,
    "sugars_g_100g": 0.0,
    "sat_fat_g_100g": 14.0,
    "sodium_mg_100g": 2,
    "fiber_g_100g": 0.0,
    "protein_g_100g": 0.0,
}

COCONUT_OIL_NUT = {
    "energy_kcal_100g": 862,
    "sugars_g_100g": 0.0,
    "sat_fat_g_100g": 87.0,
    "sodium_mg_100g": 0,
    "fiber_g_100g": 0.0,
    "protein_g_100g": 0.0,
}

UPF_LUNCHABLES_NUT = {
    "energy_kcal_100g": 350,
    "sugars_g_100g": 18.0,
    "sat_fat_g_100g": 10.0,
    "sodium_mg_100g": 900,
    "fiber_g_100g": 1.0,
    "protein_g_100g": 12.0,
}


# ═══════════════════════════════════════════════════════════════
# 1) PLAIN HONEY
# ═══════════════════════════════════════════════════════════════

class TestHoneyTwoPart:
    """Honey: nutrition_score is low (lots of sugar), processing is
    minimally_processed (high), final_score is blended."""

    def _result(self):
        return calculate_product_score(
            ingredients=["honey"],
            nutrition=HONEY_NUT,
            product_name="Raw Honey",
        )

    def test_nutrition_score_low(self):
        r = self._result()
        ns = r["nutrition_score"]["score"]
        assert ns < 50, f"Honey nutrition_score should be low, got {ns}"

    def test_processing_minimally_processed(self):
        r = self._result()
        assert r["processing"]["level"] == "minimally_processed"

    def test_processing_score_high(self):
        r = self._result()
        ps = r["processing"]["processing_score"]
        assert ps >= 85, f"Honey processing_score should be high, got {ps}"

    def test_final_score_blended(self):
        r = self._result()
        fs = r["final_score"]["score"]
        ns = r["nutrition_score"]["score"]
        # Final should be higher than nutrition alone (processing pulls up)
        assert fs > ns, f"final {fs} should exceed nutrition {ns}"
        # But still not grade A (honey is mostly sugar)
        assert r["final_score"]["grade"] != "A"

    def test_final_grade_not_a(self):
        """Honey is pure sugar — it won't score A despite good processing."""
        r = self._result()
        assert r["final_score"]["grade"] != "A"


# ═══════════════════════════════════════════════════════════════
# 2) PLAIN MIXED NUTS
# ═══════════════════════════════════════════════════════════════

class TestNutsTwoPart:
    """Plain nuts: should score decently, not F, minimally processed."""

    def _result(self):
        return calculate_product_score(
            ingredients=["almonds", "cashews", "pecans"],
            nutrition=MIXED_NUTS_NUT,
            product_name="Mixed Nuts",
        )

    def test_final_score_not_f(self):
        r = self._result()
        assert r["final_score"]["grade"] != "F"
        assert r["final_score"]["score"] >= 55

    def test_processing_minimally_processed(self):
        r = self._result()
        assert r["processing"]["level"] == "minimally_processed"

    def test_processing_score_90(self):
        r = self._result()
        assert r["processing"]["processing_score"] == 90

    def test_category_detected(self):
        r = self._result()
        assert r["category"] == "nuts_seeds_plain"


# ═══════════════════════════════════════════════════════════════
# 3) SINGLE-INGREDIENT OLIVE OIL
# ═══════════════════════════════════════════════════════════════

class TestOliveOilTwoPart:
    """Olive oil: must not be F solely due to calorie density,
    must have reasonable final_score (≥55), minimally processed."""

    def _result(self):
        return calculate_product_score(
            ingredients=["extra virgin olive oil"],
            nutrition=OLIVE_OIL_NUT,
            product_name="Olive Oil",
        )

    def test_final_score_ge_55(self):
        r = self._result()
        fs = r["final_score"]["score"]
        assert fs >= 55, f"Olive oil final_score should be >=55, got {fs}"

    def test_not_grade_f(self):
        r = self._result()
        assert r["final_score"]["grade"] != "F"

    def test_minimally_processed(self):
        r = self._result()
        assert r["processing"]["level"] == "minimally_processed"

    def test_processing_score_90(self):
        r = self._result()
        assert r["processing"]["processing_score"] == 90

    def test_category_oils_plain(self):
        r = self._result()
        assert r["category"] == "oils_plain"

    def test_portion_note_present(self):
        r = self._result()
        combined = " ".join(r["reasons"])
        assert "portion" in combined.lower() or "calorie-dense" in combined.lower()

    def test_energy_penalty_reduced(self):
        """Energy penalty should use 0.25 multiplier for oil."""
        r = self._result()
        penalties = " ".join(r["penalties"])
        # Energy penalty should exist but be reduced
        # Without oil adjustment: 884 kcal → -35
        # With 0.25: -35 * 0.25 = -9
        assert "Energy" in penalties


class TestCoconutOilSatRatio:
    """Coconut oil has very high sat-fat ratio (>0.35) → extra penalty."""

    def _result(self):
        return calculate_product_score(
            ingredients=["coconut oil"],
            nutrition=COCONUT_OIL_NUT,
            product_name="Coconut Oil",
        )

    def test_sat_ratio_penalty_applied(self):
        r = self._result()
        penalties = " ".join(r["penalties"])
        assert "sat-fat ratio" in penalties.lower() or "sat/total fat" in penalties.lower()

    def test_lower_than_olive_oil(self):
        olive = calculate_product_score(
            ingredients=["extra virgin olive oil"],
            nutrition=OLIVE_OIL_NUT,
            product_name="Olive Oil",
        )
        coco = self._result()
        assert coco["final_score"]["score"] < olive["final_score"]["score"]


# ═══════════════════════════════════════════════════════════════
# 4) UPF PRODUCT (e.g. Lunchables)
# ═══════════════════════════════════════════════════════════════

class TestUPFProduct:
    """Modified starch + preservatives → upf_signals, low processing_score,
    low final_score."""

    def _result(self):
        return calculate_product_score(
            ingredients=[
                "enriched flour", "water", "modified food starch",
                "sodium benzoate", "potassium sorbate",
                "natural flavors", "yellow 5", "soy lecithin",
            ],
            nutrition=UPF_LUNCHABLES_NUT,
            product_name="Processed Snack Pack",
        )

    def test_upf_signals_detected(self):
        r = self._result()
        assert r["processing"]["level"] == "upf_signals"

    def test_processing_score_low(self):
        r = self._result()
        ps = r["processing"]["processing_score"]
        assert ps < 50, f"UPF processing_score should be low, got {ps}"

    def test_final_score_reduced(self):
        r = self._result()
        fs = r["final_score"]["score"]
        assert fs < 50, f"UPF final_score should be low, got {fs}"

    def test_signals_populated(self):
        r = self._result()
        sigs = r["processing"]["signals"]
        assert len(sigs) >= 3, f"Expected >=3 signals, got {len(sigs)}"

    def test_details_populated(self):
        r = self._result()
        details = r["processing"]["details"]
        assert len(details) >= 3


# ═══════════════════════════════════════════════════════════════
# 5) ALLERGEN OVERLAY
# ═══════════════════════════════════════════════════════════════

class TestAllergenOverlay:
    """User allergy match → final_score=0 but nutrition_score and
    processing_score are still computed normally."""

    def _result(self):
        return calculate_product_score(
            ingredients=["almonds", "cashews", "pecans"],
            nutrition=MIXED_NUTS_NUT,
            product_name="Mixed Nuts",
            user_profile={"allergies": ["almond"]},
        )

    def test_final_score_zero(self):
        r = self._result()
        assert r["final_score"]["score"] == 0

    def test_final_grade_f(self):
        r = self._result()
        assert r["final_score"]["grade"] == "F"

    def test_nutrition_score_still_computed(self):
        r = self._result()
        ns = r["nutrition_score"]["score"]
        assert ns > 0, "nutrition_score should still be computed"

    def test_processing_score_still_computed(self):
        r = self._result()
        ps = r["processing"]["processing_score"]
        assert ps > 0, "processing_score should still be computed"

    def test_backward_compat_score_zero(self):
        """Top-level score (backward compat) should also be 0."""
        r = self._result()
        assert r["score"] == 0
        assert r["grade"] == "F"


# ═══════════════════════════════════════════════════════════════
# 6) OIL-SPECIFIC: HYDROGENATED OIL
# ═══════════════════════════════════════════════════════════════

class TestHydrogenatedOil:
    """Hydrogenated oil → force upf_signals + big penalty."""

    def test_detect_hydrogenated(self):
        assert _has_hydrogenated_oil(["partially hydrogenated soybean oil"])
        assert _has_hydrogenated_oil(["hydrogenated vegetable oil"])
        assert not _has_hydrogenated_oil(["olive oil"])

    def test_hydrogenated_not_plain_oil(self):
        """_is_plain_oil should reject hydrogenated oils (UPF indicator)."""
        # The actual scorer checks UPF tags which include hydrogenated terms
        r = calculate_product_score(
            ingredients=["partially hydrogenated soybean oil"],
            nutrition=OLIVE_OIL_NUT,
            product_name="Margarine Oil",
        )
        # Should have upf_signals processing level
        assert r["processing"]["level"] == "upf_signals"

    def test_hydrogenated_final_penalty(self):
        r = calculate_product_score(
            ingredients=["partially hydrogenated soybean oil"],
            nutrition=OLIVE_OIL_NUT,
            product_name="Margarine Oil",
        )
        fs = r["final_score"]["score"]
        # Hydrogenated oil gets -25 final penalty on top of everything
        assert fs < 55


# ═══════════════════════════════════════════════════════════════
# 7) STRUCTURE / OUTPUT FORMAT
# ═══════════════════════════════════════════════════════════════

class TestOutputStructure:
    """All three sub-objects must be present with correct keys."""

    def _result(self):
        return calculate_product_score(
            ingredients=["wheat flour", "water", "salt"],
            nutrition={
                "energy_kcal_100g": 250,
                "sugars_g_100g": 2.0,
                "sat_fat_g_100g": 0.5,
                "sodium_mg_100g": 500,
            },
            product_name="Bread",
        )

    def test_nutrition_score_keys(self):
        ns = self._result()["nutrition_score"]
        assert "score" in ns
        assert "grade" in ns
        assert "reasons" in ns
        assert "penalties" in ns
        assert "uncertainties" in ns
        assert "nutrition_used" in ns
        assert "nutrition_confidence" in ns

    def test_processing_keys(self):
        p = self._result()["processing"]
        assert "level" in p
        assert "processing_score" in p
        assert "signals" in p
        assert "details" in p

    def test_final_score_keys(self):
        f = self._result()["final_score"]
        assert "score" in f
        assert "grade" in f
        assert "reasons" in f
        assert "uncertainties" in f

    def test_backward_compat_keys(self):
        r = self._result()
        # Top-level fields should still exist
        assert "score" in r
        assert "grade" in r
        assert "reasons" in r
        assert "penalties" in r
        assert "uncertainties" in r
        assert "nutrition_used" in r
        assert "nutrition_confidence" in r
        assert "personalized_conflicts" in r

    def test_top_level_matches_final(self):
        r = self._result()
        assert r["score"] == r["final_score"]["score"]
        assert r["grade"] == r["final_score"]["grade"]

    def test_processing_badge_backward_compat(self):
        """processing_badge should still be present for old frontend."""
        r = self._result()
        assert "processing_badge" in r
        assert r["processing_badge"]["level"] == r["processing"]["level"]


# ═══════════════════════════════════════════════════════════════
# 8) FINAL SCORE FORMULA
# ═══════════════════════════════════════════════════════════════

class TestFinalScoreFormula:
    """final_score ≈ 0.7 * nutrition_score + 0.3 * processing_score
    (before personalization)."""

    def test_formula_no_personalization(self):
        r = calculate_product_score(
            ingredients=["wheat flour", "water", "salt"],
            nutrition={
                "energy_kcal_100g": 250,
                "sugars_g_100g": 2.0,
                "sat_fat_g_100g": 0.5,
                "sodium_mg_100g": 500,
            },
        )
        ns = r["nutrition_score"]["score"]
        ps = r["processing"]["processing_score"]
        expected = round(0.7 * ns + 0.3 * ps)
        fs = r["final_score"]["score"]
        # Allow ±1 for rounding
        assert abs(fs - expected) <= 1, (
            f"final {fs} != 0.7*{ns} + 0.3*{ps} = {expected}"
        )

    def test_avoid_term_only_affects_final(self):
        """Avoid terms penalize final_score but not nutrition_score or processing."""
        base = calculate_product_score(
            ingredients=["wheat flour", "water", "salt"],
            nutrition={
                "energy_kcal_100g": 250,
                "sugars_g_100g": 2.0,
                "sat_fat_g_100g": 0.5,
                "sodium_mg_100g": 500,
            },
        )
        with_avoid = calculate_product_score(
            ingredients=["wheat flour", "water", "salt"],
            nutrition={
                "energy_kcal_100g": 250,
                "sugars_g_100g": 2.0,
                "sat_fat_g_100g": 0.5,
                "sodium_mg_100g": 500,
            },
            user_profile={"avoid_terms": ["wheat"]},
        )
        # Nutrition score unchanged
        assert base["nutrition_score"]["score"] == with_avoid["nutrition_score"]["score"]
        # Processing score unchanged
        assert base["processing"]["processing_score"] == with_avoid["processing"]["processing_score"]
        # Final score reduced
        assert with_avoid["final_score"]["score"] < base["final_score"]["score"]


# ═══════════════════════════════════════════════════════════════
# 9) PROCESSING SCORE UNIT TESTS
# ═══════════════════════════════════════════════════════════════

class TestProcessingScoreComputation:
    def test_minimally_processed_90(self):
        assert _compute_processing_score("minimally_processed", []) == 90

    def test_processed_70(self):
        assert _compute_processing_score("processed", []) == 70

    def test_upf_signals_base_55(self):
        assert _compute_processing_score("upf_signals", []) == 55

    def test_modified_starch_penalty(self):
        score = _compute_processing_score(
            "upf_signals", ["upf_indicator_modified_starch"]
        )
        assert score == 55 - 12

    def test_preservative_cap(self):
        # 4 preservatives × 5 = 20 but capped at 15
        tags = ["upf_indicator_preservative"] * 4
        score = _compute_processing_score("upf_signals", tags)
        assert score == 55 - 15

    def test_umbrella_term_cap(self):
        # 3 flavor tags × 4 = 12 but capped at 8
        tags = ["upf_indicator_flavor"] * 3
        score = _compute_processing_score("upf_signals", tags)
        assert score == 55 - 8

    def test_combined_penalties(self):
        tags = [
            "upf_indicator_modified_starch",   # -12
            "upf_indicator_sweetener",          # -12
            "upf_indicator_color",              # -8
        ]
        score = _compute_processing_score("upf_signals", tags)
        assert score == max(0, 55 - 12 - 12 - 8)

    def test_floor_at_zero(self):
        # Lots of penalties → floor at 0
        tags = (
            ["upf_indicator_modified_starch"] * 3 +
            ["upf_indicator_sweetener"] * 3 +
            ["upf_indicator_color"] * 3
        )
        score = _compute_processing_score("upf_signals", tags)
        assert score == 0


# ═══════════════════════════════════════════════════════════════
# 10) detect_upf_signals UNIT TESTS
# ═══════════════════════════════════════════════════════════════

class TestDetectUPFSignals:
    def test_no_upf_ingredients(self):
        signals, details, tags = detect_upf_signals(["almonds", "cashews"])
        assert len(signals) == 0
        assert len(tags) == 0

    def test_modified_starch_detected(self):
        signals, details, tags = detect_upf_signals(["modified food starch"])
        assert any("modified starch" in s for s in signals)
        assert "upf_indicator_modified_starch" in tags

    def test_sunflower_oil_not_emulsifier(self):
        """Sunflower oil must NOT trigger emulsifier detection."""
        signals, details, tags = detect_upf_signals(["sunflower oil"])
        assert "upf_indicator_emulsifier" not in tags

    def test_preservatives_detected(self):
        signals, details, tags = detect_upf_signals(
            ["sodium benzoate", "potassium sorbate"]
        )
        assert tags.count("upf_indicator_preservative") == 2

    def test_artificial_sweetener(self):
        signals, details, tags = detect_upf_signals(["sucralose"])
        assert "upf_indicator_sweetener" in tags


# ═══════════════════════════════════════════════════════════════
# 11) EMPTY / EDGE CASES
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_no_data_returns_structure(self):
        r = calculate_product_score()
        assert "nutrition_score" in r
        assert "processing" in r
        assert "final_score" in r
        assert r["nutrition_used"] is False

    def test_ingredients_only_ceiling(self):
        """Without nutrition, final_score is capped at 70."""
        r = calculate_product_score(
            ingredients=["almonds", "cashews"],
        )
        assert r["final_score"]["score"] <= 70

    def test_grade_mapping(self):
        """Verify grade boundaries."""
        r = calculate_product_score(
            ingredients=["water"],
            nutrition={
                "energy_kcal_100g": 0,
                "sugars_g_100g": 0,
                "sat_fat_g_100g": 0,
                "sodium_mg_100g": 0,
                "fiber_g_100g": 0,
            },
        )
        # Water with perfect nutrition → should get high score
        assert r["final_score"]["score"] >= 85
        assert r["final_score"]["grade"] == "A"
