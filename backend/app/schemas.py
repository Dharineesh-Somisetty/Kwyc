"""LabelLens – Pydantic schemas (API + Gemini structured output contracts)."""

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
# Ingredient item (from Gemini structuring)
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
# Product score (from scorer.py)
# ──────────────────────────────────────────────
class ProductScore(BaseModel):
    score: float = 50.0
    grade: str = "C"
    reasons_good: List[str] = Field(default_factory=list)
    reasons_bad: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    personalized_conflicts: List[str] = Field(default_factory=list)

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
    product_score: Optional[ProductScore] = None
    personalized_summary: str = ""
    disclaimer: str = "Educational only; not medical advice."

# ──────────────────────────────────────────────
# Gemini structured output models
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

