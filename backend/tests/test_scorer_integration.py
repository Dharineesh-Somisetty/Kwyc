"""Tests for the product scoring engine."""

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
        for key in ("score", "grade", "reasons_good", "reasons_bad", "uncertainties", "personalized_conflicts"):
            assert key in result

    def test_empty_ingredients_returns_default(self):
        result = calculate_product_score([])
        assert result["score"] == 50.0
        assert result["grade"] == "C"


# ── KB entries integration ─────────────────────────────────────────
class TestKBEntries:
    def test_matched_entries_used(self):
        matched = {
            "sugar": {"tags": ["added-sugar"]},
            "fiber": {"tags": ["fiber"]},
        }
        result = calculate_product_score(["sugar", "fiber"], matched_entries=matched)
        assert 0 <= result["score"] <= 100
        # Sugar penalty should pull score below 100
        assert result["score"] < 100

    def test_empty_matched_entries(self):
        result = calculate_product_score(["water", "salt"], matched_entries={})
        assert 0 <= result["score"] <= 100


# ── User profile / allergy ─────────────────────────────────────────
class TestUserProfile:
    def test_allergy_conflict_returns_zero(self):
        profile = {"allergies": ["milk"]}
        result = calculate_product_score(
            ["whole milk powder", "sugar"],
            user_profile=profile,
        )
        assert result["score"] == 0.0
        assert result["grade"] == "F"
        assert len(result["personalized_conflicts"]) > 0

    def test_vegan_conflict_noted(self):
        matched = {"whey protein": {"tags": ["dairy", "animal-derived"]}}
        profile = {"vegan": True}
        result = calculate_product_score(
            ["whey protein", "oats"],
            matched_entries=matched,
            user_profile=profile,
        )
        assert any("vegan" in c.lower() or "Vegan" in c for c in result["personalized_conflicts"])

    def test_no_profile_no_conflicts(self):
        result = calculate_product_score(["water", "salt"])
        assert result["personalized_conflicts"] == []


# ── Scoring heuristics ─────────────────────────────────────────────
class TestScoringHeuristics:
    def test_healthy_product_scores_high(self):
        result = calculate_product_score(["water", "oats", "almonds"])
        assert result["score"] >= 80

    def test_junk_product_scores_low(self):
        result = calculate_product_score([
            "sugar", "high fructose corn syrup", "red 40",
            "sodium benzoate", "natural flavors",
        ])
        assert result["score"] < 75

    def test_umbrella_term_adds_uncertainty(self):
        result = calculate_product_score(["natural flavors", "water"])
        assert any("umbrella" in u.lower() or "natural flavor" in u.lower() for u in result["uncertainties"])
