"""Tests for label extraction pipeline: nutrition normalization, integration, regression."""

import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock

from app.schemas import NutritionFacts, LabelExtraction
from app.main import nutrition_to_per_100g


# ──────────────────────────────────────────────
# Unit tests: nutrition_to_per_100g
# ──────────────────────────────────────────────

class TestNutritionToPer100g:
    """Convert per-serving NutritionFacts to per-100g scoring dict."""

    def test_cola_can_355ml(self):
        """Coca-Cola can: 355 ml serving → per-100g values."""
        nf = NutritionFacts(
            serving_size_text="1 can (355ml)",
            serving_size_value=355,
            serving_size_unit="ml",
            calories=190,
            total_sugars_g=52,
            sodium_mg=60,
            saturated_fat_g=0,
            fiber_g=0,
            protein_g=0,
            confidence=0.9,
        )
        result, notes = nutrition_to_per_100g(nf)
        assert result is not None
        assert len(notes) == 0

        # 190 * (100/355) ≈ 53.5
        assert abs(result["energy_kcal_100g"] - 53.5) < 1.0
        # 52 * (100/355) ≈ 14.6
        assert abs(result["sugars_g_100g"] - 14.6) < 1.0
        # 60 * (100/355) ≈ 16.9
        assert abs(result["sodium_mg_100g"] - 16.9) < 1.0
        assert result["source"] == "label_photo"

    def test_cereal_serving_39g(self):
        """39g cereal serving."""
        nf = NutritionFacts(
            serving_size_value=39,
            serving_size_unit="g",
            calories=150,
            total_sugars_g=12,
            saturated_fat_g=0.5,
            sodium_mg=220,
            fiber_g=3,
            protein_g=2,
            confidence=0.8,
        )
        result, notes = nutrition_to_per_100g(nf)
        assert result is not None
        factor = 100.0 / 39
        assert abs(result["energy_kcal_100g"] - round(150 * factor, 1)) < 0.2
        assert abs(result["sugars_g_100g"] - round(12 * factor, 1)) < 0.2

    def test_missing_serving_size_value(self):
        """No serving_size_value → cannot normalize."""
        nf = NutritionFacts(
            serving_size_unit="g",
            calories=100,
        )
        result, notes = nutrition_to_per_100g(nf)
        assert result is None
        assert any("missing" in n.lower() for n in notes)

    def test_zero_serving_size(self):
        """serving_size_value=0 → cannot normalize."""
        nf = NutritionFacts(
            serving_size_value=0,
            serving_size_unit="g",
            calories=100,
        )
        result, notes = nutrition_to_per_100g(nf)
        assert result is None

    def test_non_metric_unit(self):
        """Unit is 'oz' → cannot normalize."""
        nf = NutritionFacts(
            serving_size_value=1.0,
            serving_size_unit="oz",
            calories=100,
        )
        result, notes = nutrition_to_per_100g(nf)
        assert result is None
        assert any("oz" in n for n in notes)

    def test_no_numeric_values(self):
        """Serving size present but all nutrients None → returns None."""
        nf = NutritionFacts(
            serving_size_value=100,
            serving_size_unit="g",
        )
        result, notes = nutrition_to_per_100g(nf)
        assert result is None
        assert any("no numeric" in n.lower() for n in notes)

    def test_partial_nutrients(self):
        """Only some nutrients present → still normalizes the ones available."""
        nf = NutritionFacts(
            serving_size_value=200,
            serving_size_unit="ml",
            calories=80,
            total_sugars_g=10,
            # everything else None
        )
        result, notes = nutrition_to_per_100g(nf)
        assert result is not None
        assert result["energy_kcal_100g"] == round(80 * 0.5, 1)
        assert result["sugars_g_100g"] == round(10 * 0.5, 1)
        assert result["sat_fat_g_100g"] is None
        assert result["source"] == "label_photo"


# ──────────────────────────────────────────────
# Integration test: /api/scan/label with mocked Groq
# ──────────────────────────────────────────────

class TestScanLabelIntegration:
    """Test the /api/scan/label endpoint with monkeypatched Groq extraction."""

    @pytest.fixture
    def client(self):
        """Create a test client with mocked Groq services."""
        from app.schemas import (
            StructuredIngredientsResult,
            IngredientItem,
            PersonalizedSummaryResult,
        )

        with patch("app.main.groq_structure_ingredients") as mock_struct, \
             patch("app.main.groq_personalized_explain") as mock_explain, \
             patch("app.main.extract_label_sections") as mock_extract:

            # Mock Groq extraction
            mock_extract.return_value = LabelExtraction(
                ingredients_text="carbonated water, sugar, caramel color, phosphoric acid, natural flavors, caffeine",
                ingredients_confidence=0.9,
                nutrition=NutritionFacts(
                    serving_size_text="1 can (355ml)",
                    serving_size_value=355,
                    serving_size_unit="ml",
                    calories=190,
                    total_sugars_g=52,
                    saturated_fat_g=0,
                    sodium_mg=60,
                    fiber_g=0,
                    protein_g=0,
                    confidence=0.85,
                ),
                nutrition_confidence=0.85,
                missing_sections=[],
                overall_confidence=0.87,
            )

            # Mock Groq structure
            mock_struct.return_value = StructuredIngredientsResult(
                ingredients=[
                    IngredientItem(name_raw="carbonated water", name_canonical="carbonated water"),
                    IngredientItem(name_raw="sugar", name_canonical="sugar"),
                    IngredientItem(name_raw="caramel color", name_canonical="caramel color"),
                    IngredientItem(name_raw="phosphoric acid", name_canonical="phosphoric acid"),
                    IngredientItem(name_raw="natural flavors", name_canonical="natural flavors"),
                    IngredientItem(name_raw="caffeine", name_canonical="caffeine"),
                ],
                umbrella_terms=["natural flavors"],
                allergen_statements=[],
            )

            # Mock Groq summary
            mock_explain.return_value = PersonalizedSummaryResult(
                summary="This cola product is high in sugar.",
                citations_used=[],
            )

            from fastapi.testclient import TestClient
            from app.main import app

            yield TestClient(app)

    def test_label_scan_returns_nutrition(self, client):
        """Verify scan/label returns extraction, nutrition, nutrition_100g, and score."""
        dummy_image = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # minimal JPEG-like bytes

        response = client.post(
            "/api/scan/label",
            files={"image": ("label.jpg", dummy_image, "image/jpeg")},
            data={"user_profile": "{}"},
        )
        assert response.status_code == 200
        body = response.json()

        # extraction present
        assert body.get("extraction") is not None
        assert body["extraction"]["ingredients_text"] is not None
        assert body["extraction"]["ingredients_confidence"] > 0

        # nutrition_per_serving present
        assert body.get("nutrition_per_serving") is not None
        assert body["nutrition_per_serving"]["calories"] == 190

        # nutrition_100g normalized
        assert body.get("nutrition_100g") is not None
        assert abs(body["nutrition_100g"]["energy_kcal_100g"] - 53.5) < 1.0
        assert abs(body["nutrition_100g"]["sugars_g_100g"] - 14.6) < 1.0

        # product_score used nutrition
        assert body.get("product_score") is not None
        assert body["product_score"]["nutrition_confidence"] == "high"

    def test_label_scan_no_nutrition(self, client):
        """When Groq returns no nutrition, score uses ingredient-only fallback."""
        with patch("app.main.extract_label_sections") as mock_extract:
            mock_extract.return_value = LabelExtraction(
                ingredients_text="whole wheat flour, water, salt, yeast",
                ingredients_confidence=0.8,
                nutrition=None,
                nutrition_confidence=0.0,
                missing_sections=["nutrition"],
                overall_confidence=0.5,
            )

            with patch("app.main.groq_structure_ingredients") as mock_struct, \
                 patch("app.main.groq_personalized_explain") as mock_explain:
                from app.schemas import (
                    StructuredIngredientsResult,
                    IngredientItem,
                    PersonalizedSummaryResult,
                )
                mock_struct.return_value = StructuredIngredientsResult(
                    ingredients=[
                        IngredientItem(name_raw="whole wheat flour", name_canonical="whole wheat flour"),
                        IngredientItem(name_raw="water", name_canonical="water"),
                        IngredientItem(name_raw="salt", name_canonical="salt"),
                        IngredientItem(name_raw="yeast", name_canonical="yeast"),
                    ],
                )
                mock_explain.return_value = PersonalizedSummaryResult(
                    summary="Simple bread ingredients.",
                    citations_used=[],
                )

                dummy_image = b"\xff\xd8\xff\xe0" + b"\x00" * 100
                response = client.post(
                    "/api/scan/label",
                    files={"image": ("label.jpg", dummy_image, "image/jpeg")},
                    data={"user_profile": "{}"},
                )
                assert response.status_code == 200
                body = response.json()

                assert body.get("nutrition_100g") is None
                assert body.get("nutrition_per_serving") is None
                assert body["product_score"]["nutrition_confidence"] == "low"


# ──────────────────────────────────────────────
# Regression test: no nutrition → score capped
# ──────────────────────────────────────────────

class TestRegressionNoNutrition:
    """When nutrition is missing, ingredient-only scoring applies."""

    def test_ingredient_only_not_grade_a(self):
        """Sugar-heavy ingredients without nutrition should not score A."""
        from app.services.scorer import calculate_product_score

        result = calculate_product_score(
            ingredients=["sugar", "corn syrup", "palm oil", "artificial flavor"],
        )
        assert result["grade"] != "A"
        assert result["score"] <= 80
        assert result["nutrition_confidence"] == "low"

    def test_clean_ingredients_no_nutrition_still_reasonable(self):
        """Clean ingredients without nutrition get a conservative-capped score."""
        from app.services.scorer import calculate_product_score

        result = calculate_product_score(
            ingredients=["whole wheat flour", "water", "salt", "yeast"],
        )
        # Without nutrition, score is capped at 70
        assert result["score"] <= 70
        assert result["score"] >= 60
        assert result["nutrition_confidence"] == "low"
        assert result["nutrition_used"] is False


# ──────────────────────────────────────────────
# Unit test: groq_service parsing
# ──────────────────────────────────────────────

class TestGroqServiceParsing:
    """Test _parse_extraction tolerates various input shapes."""

    def test_parse_full_response(self):
        from app.services.groq_service import _parse_extraction

        data = {
            "ingredients_text": "water, sugar, salt",
            "ingredients_confidence": 0.9,
            "nutrition": {
                "serving_size_value": 100,
                "serving_size_unit": "g",
                "calories": 200,
                "total_sugars_g": 15,
                "confidence": 0.8,
            },
            "nutrition_confidence": 0.8,
            "missing_sections": [],
            "overall_confidence": 0.85,
        }
        result = _parse_extraction(data)
        assert result.ingredients_text == "water, sugar, salt"
        assert result.nutrition is not None
        assert result.nutrition.calories == 200
        assert result.overall_confidence == 0.85

    def test_parse_missing_nutrition(self):
        from app.services.groq_service import _parse_extraction

        data = {
            "ingredients_text": "water, sugar",
            "ingredients_confidence": 0.9,
            "nutrition": None,
            "nutrition_confidence": 0.0,
            "missing_sections": ["nutrition"],
            "overall_confidence": 0.5,
        }
        result = _parse_extraction(data)
        assert result.nutrition is None
        assert "nutrition" in result.missing_sections

    def test_parse_empty_dict(self):
        from app.services.groq_service import _parse_extraction

        result = _parse_extraction({})
        assert result.ingredients_text is None
        assert result.nutrition is None
        assert result.overall_confidence == 0.0

    def test_fallback_extraction(self):
        from app.services.groq_service import _fallback_extraction

        result = _fallback_extraction("test error")
        assert result.ingredients_text is None
        assert result.nutrition is None
        assert "ingredients" in result.missing_sections
        assert "nutrition" in result.missing_sections
        assert result.overall_confidence == 0.0
