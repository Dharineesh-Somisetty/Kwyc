"""LabelLens – Pydantic schemas (API + LLM structured output contracts)."""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid, datetime

# ──────────────────────────────────────────────
# User Profile (sent by frontend with every scan)
# ──────────────────────────────────────────────
class UserProfile(BaseModel):
    vegan: bool = False
    vegetarian: bool = False
    halal: bool = False
    allergies: List[str] = Field(default_factory=list)
    caffeine_limit_mg: Optional[int] = None
    avoid_terms: List[str] = Field(default_factory=list)

# ──────────────────────────────────────────────
# Evidence / Knowledge‑base snippets
# ──────────────────────────────────────────────
class EvidenceSnippet(BaseModel):
    citation_id: str
    title: str
    snippet: str
    source_url: str

# ──────────────────────────────────────────────
# Ingredient item (from LLM structuring)
# ──────────────────────────────────────────────
class IngredientItem(BaseModel):
    name_raw: str
    name_canonical: str
    confidence: float = Field(ge=0, le=1, default=1.0)
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

# ──────────────────────────────────────────────
# Flags (deterministic rules engine output)
# ──────────────────────────────────────────────
class Flag(BaseModel):
    type: str                         # allergen | diet_conflict | caffeine | umbrella_term | avoid_term
    severity: str = "info"            # info | warn | high
    message: str
    related_ingredients: List[str] = Field(default_factory=list)
    citation_ids: List[str] = Field(default_factory=list)

# ──────────────────────────────────────────────
# Nutrition (from OpenFoodFacts / label)
# ──────────────────────────────────────────────
class Nutrition(BaseModel):
    energy_kcal_100g: Optional[float] = None
    sugars_g_100g: Optional[float] = None
    sat_fat_g_100g: Optional[float] = None
    sodium_mg_100g: Optional[float] = None
    fiber_g_100g: Optional[float] = None
    protein_g_100g: Optional[float] = None
    source: str = "openfoodfacts"
    uncertainties: List[str] = Field(default_factory=list)

# ──────────────────────────────────────────────
# Nutrition Facts (extracted from label photo)
# ──────────────────────────────────────────────
class NutritionFacts(BaseModel):
    serving_size_text: Optional[str] = None
    serving_size_value: Optional[float] = None
    serving_size_unit: Optional[str] = None        # g, ml, oz, etc.
    servings_per_container: Optional[float] = None

    calories: Optional[float] = None
    total_fat_g: Optional[float] = None
    saturated_fat_g: Optional[float] = None
    trans_fat_g: Optional[float] = None
    cholesterol_mg: Optional[float] = None
    sodium_mg: Optional[float] = None
    total_carbs_g: Optional[float] = None
    fiber_g: Optional[float] = None
    total_sugars_g: Optional[float] = None
    added_sugars_g: Optional[float] = None
    protein_g: Optional[float] = None

    is_per_serving: bool = True
    notes: List[str] = Field(default_factory=list)
    confidence: float = 0.0

class LabelExtraction(BaseModel):
    ingredients_text: Optional[str] = None
    ingredients_confidence: float = 0.0

    nutrition: Optional[NutritionFacts] = None
    nutrition_confidence: float = 0.0

    missing_sections: List[str] = Field(default_factory=list)
    overall_confidence: float = 0.0

# ──────────────────────────────────────────────
# Portion-sensitive info
# ──────────────────────────────────────────────
class PortionInfo(BaseModel):
    portion_sensitive: bool = False
    typical_serving_text: Optional[str] = None   # e.g. "1 Tbsp (21g)"
    note: Optional[str] = None                   # e.g. "Typically consumed in small amounts."

# ──────────────────────────────────────────────
# Nutrition score / processing / final score (split outputs v2)
# ──────────────────────────────────────────────
class NutritionScoreInfo(BaseModel):
    score: int = 50
    grade: str = "C"
    reasons: List[str] = Field(default_factory=list)
    penalties: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    nutrition_used: bool = False
    nutrition_confidence: str = "low"  # high | medium | low
    basis: str = "100g"                # "100g" or "serving"

class ProcessingInfo(BaseModel):
    level: str = "processed"   # minimally_processed | processed | upf_signals
    processing_score: int = 70
    signals: List[str] = Field(default_factory=list)
    details: List[str] = Field(default_factory=list)

class FinalScoreInfo(BaseModel):
    score: int = 50
    grade: str = "C"
    reasons: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)

# Backward compat alias
class ProcessingBadge(BaseModel):
    level: str = "processed"
    signals: List[str] = Field(default_factory=list)

# ──────────────────────────────────────────────
# Product score (from scorer.py)
# ──────────────────────────────────────────────
class ProductScore(BaseModel):
    score: int = 50
    grade: str = "C"
    reasons: List[str] = Field(default_factory=list)
    penalties: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    personalized_conflicts: List[str] = Field(default_factory=list)
    nutrition_used: bool = False
    nutrition_confidence: str = "low"
    beverage_label: bool = False
    beverage_reason: str = ""
    # Split outputs (v2)
    nutrition_score: Optional[NutritionScoreInfo] = None
    processing: Optional[ProcessingInfo] = None
    processing_badge: Optional[ProcessingBadge] = None   # backward compat
    final_score: Optional[FinalScoreInfo] = None
    category: Optional[str] = None
    ingredients_inferred: bool = False
    # Portion-sensitive scoring (v3)
    nutrition_score_100g: Optional[NutritionScoreInfo] = None
    nutrition_score_serving: Optional[NutritionScoreInfo] = None
    primary_nutrition_view: str = "100g"   # "100g" or "serving"
    portion_info: Optional[PortionInfo] = None

# ──────────────────────────────────────────────
# Full analysis result returned to frontend
# ──────────────────────────────────────────────
class ProductMeta(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    barcode: Optional[str] = None

class AnalysisResult(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    product: ProductMeta = Field(default_factory=ProductMeta)
    ingredients_raw_text: str = ""
    ingredients: List[IngredientItem] = Field(default_factory=list)
    umbrella_terms: List[str] = Field(default_factory=list)
    allergen_statements: List[str] = Field(default_factory=list)
    flags: List[Flag] = Field(default_factory=list)
    evidence: List[EvidenceSnippet] = Field(default_factory=list)
    nutrition: Optional[Nutrition] = None
    product_score: Optional[ProductScore] = None
    personalized_summary: str = ""
    disclaimer: str = "Educational only; not medical advice."
    # Label extraction additions (backward-compatible)
    extraction: Optional[LabelExtraction] = None
    nutrition_per_serving: Optional[NutritionFacts] = None
    nutrition_100g: Optional[dict] = None
    # Nutrition provenance (set by barcode endpoint)
    nutrition_status: Optional[str] = None    # verified_barcode|extracted_photo|not_detected
    nutrition_source: Optional[str] = None    # openfoodfacts|cache|None

# ──────────────────────────────────────────────
# LLM structured output models
# ──────────────────────────────────────────────
class StructuredIngredientsResult(BaseModel):
    ingredients: List[IngredientItem]
    umbrella_terms: List[str] = Field(default_factory=list)
    allergen_statements: List[str] = Field(default_factory=list)

class PersonalizedSummaryResult(BaseModel):
    summary: str
    citations_used: List[str] = Field(default_factory=list)

class ChatAnswerResult(BaseModel):
    answer: str
    citations_used: List[str] = Field(default_factory=list)

# ──────────────────────────────────────────────
# API request / response models
# ──────────────────────────────────────────────
class BarcodeScanRequest(BaseModel):
    barcode: str
    user_profile: UserProfile = Field(default_factory=UserProfile)
    profile_id: Optional[str] = None   # household profile to score for

class LabelScanRequest(BaseModel):
    """Multipart – user_profile sent as JSON string field."""
    pass  # handled via Form fields; see endpoint

class ChatRequest(BaseModel):
    session_id: str
    message: str
    chat_history: List[dict] = Field(default_factory=list)

class ChatResponse(BaseModel):
    answer: str
    citations_used: List[str] = Field(default_factory=list)
    disclaimer: str = "Educational only; not medical advice."


# ──────────────────────────────────────────────
# Household Profile CRUD schemas
# ──────────────────────────────────────────────
class ProfileCreate(BaseModel):
    name: str = "Me"
    allergies: List[str] = Field(default_factory=list)
    avoid_terms: List[str] = Field(default_factory=list)
    diet_style: Optional[str] = None          # vegan | vegetarian | halal
    is_default: bool = False

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    allergies: Optional[List[str]] = None
    avoid_terms: Optional[List[str]] = None
    diet_style: Optional[str] = None
    is_default: Optional[bool] = None

class ProfileResponse(BaseModel):
    id: str
    name: str
    allergies: List[str] = Field(default_factory=list)
    avoid_terms: List[str] = Field(default_factory=list)
    diet_style: Optional[str] = None
    is_default: bool = False
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True

