"""LabelLens – SQLAlchemy ORM models."""

from __future__ import annotations
import uuid
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, Boolean, func, JSON
from .database import Base


def _new_uuid() -> str:
    return uuid.uuid4().hex


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    product_json = Column(Text, default="{}")
    analysis_json = Column(Text, default="{}")
    user_profile_json = Column(Text, default="{}")


class ProductCache(Base):
    __tablename__ = "product_cache"

    barcode = Column(String, primary_key=True, index=True)
    product_name = Column(String, default="")
    brand = Column(String, default="")

    source = Column(String, default="label_photo")  # openfoodfacts|label_photo|mixed

    ingredients_text = Column(Text, default="")
    ingredients_json = Column(Text, default="{}")  # parsed ingredient list

    nutrition_per_serving_json = Column(Text, default="{}")  # OCR NutritionFacts
    nutrition_100g_json = Column(Text, default="{}")         # normalized for scorer

    product_score_json = Column(Text, default="{}")          # optional; can be recomputed

    nutrition_confidence = Column(String, default="low")     # high|medium|low
    extraction_confidence = Column(Float, default=0.0)

    schema_version = Column(Integer, default=1)
    scoring_version = Column(Integer, default=1)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ──────────────────────────────────────────────
# Household Profiles (per Supabase user)
# ──────────────────────────────────────────────
class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, nullable=False, index=True)  # Supabase sub
    name = Column(String, nullable=False, default="Me")
    allergies = Column(JSON, default=list)       # e.g. ["peanuts", "milk"]
    avoid_terms = Column(JSON, default=list)     # e.g. ["palm oil", "MSG"]
    diet_style = Column(String, nullable=True)   # vegan | vegetarian | halal | null
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ──────────────────────────────────────────────
# User Entitlements (Premium-ready)
# ──────────────────────────────────────────────
class UserEntitlement(Base):
    __tablename__ = "user_entitlements"

    user_id = Column(String, primary_key=True)   # Supabase sub
    plan = Column(String, default="free")        # free | premium
    max_profiles = Column(Integer, default=1)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ──────────────────────────────────────────────
# Unknown Ingredient Events (anonymized logging)
# ──────────────────────────────────────────────
class IngredientUnknownEvent(Base):
    __tablename__ = "ingredient_unknown_events"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_hash = Column(String, nullable=True)       # hashed user id, no raw email
    barcode = Column(String, nullable=True)          # product barcode if available
    unknown_rate = Column(Float, default=0.0)
    unknown_items = Column(JSON, default=list)       # normalized strings only
    fallback_items = Column(JSON, default=list)      # [{category, normalized}]
    total_count = Column(Integer, default=0)
    unknown_count = Column(Integer, default=0)
    fallback_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


# ──────────────────────────────────────────────
# User-submitted Unknown Ingredient Feedback
# ──────────────────────────────────────────────
class UnknownIngredientSubmission(Base):
    __tablename__ = "unknown_ingredient_submissions"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_hash = Column(String, nullable=True)
    ingredient_text = Column(String, nullable=False)
    normalized_text = Column(String, nullable=True)
    suggested_category = Column(String, nullable=True)
    status = Column(String, default="pending")       # pending | reviewed | added
    created_at = Column(DateTime, server_default=func.now())


# ──────────────────────────────────────────────
# Scan History (per user, for revisiting past scans)
# ──────────────────────────────────────────────
class ScanHistory(Base):
    __tablename__ = "scan_history"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, nullable=False, index=True)    # Supabase sub
    session_id = Column(String, nullable=False, index=True)  # links to sessions table
    product_name = Column(String, default="")
    brand = Column(String, default="")
    barcode = Column(String, nullable=True)
    score = Column(Integer, nullable=True)
    grade = Column(String, nullable=True)
    scan_type = Column(String, default="barcode")    # barcode | label
    profile_name = Column(String, default="")        # which profile was used
    created_at = Column(DateTime, server_default=func.now())


