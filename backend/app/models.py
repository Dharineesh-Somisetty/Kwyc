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


