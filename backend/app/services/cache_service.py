"""Barcode-based cache for OCR-extracted nutrition/ingredients.

Stores structured extraction data keyed by barcode so that future
barcode scans can reuse label-photo results when OpenFoodFacts
nutriments are missing.

Never stores raw image bytes.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session as DBSession

from ..models import ProductCache

logger = logging.getLogger("labellens.cache")

# ── Versioning constants ──────────────────────────────────────────
SCHEMA_VERSION = 1
SCORING_VERSION = 1

# Minimum number of non-null numeric nutrition fields to consider usable
_MIN_NUTRITION_FIELDS = 2

# Fields we consider "key" when checking usability of per-100g nutrition
_KEY_100G_FIELDS = (
    "energy_kcal_100g",
    "sugars_g_100g",
    "sat_fat_g_100g",
    "sodium_mg_100g",
    "fiber_g_100g",
    "protein_g_100g",
)

# Fields we consider "key" when checking usability of per-serving nutrition
_KEY_PER_SERVING_FIELDS = (
    "calories",
    "total_fat_g",
    "saturated_fat_g",
    "sodium_mg",
    "total_carbs_g",
    "fiber_g",
    "total_sugars_g",
    "protein_g",
)


# ── Helpers ───────────────────────────────────────────────────────
def _safe_json_loads(text: str | None) -> Any:
    """Parse JSON string, returning empty dict on failure."""
    if not text:
        return {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}


def _safe_json_dumps(obj: Any) -> str:
    """Serialize to JSON string, defaulting to '{}' on failure."""
    if obj is None:
        return "{}"
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return "{}"


def _count_numeric_fields(d: dict, fields: tuple[str, ...]) -> int:
    """Count how many of *fields* have a non-null numeric value in *d*."""
    count = 0
    for key in fields:
        val = d.get(key)
        if val is not None:
            try:
                float(val)
                count += 1
            except (ValueError, TypeError):
                pass
    return count


# ── Public API ────────────────────────────────────────────────────

def get_cached_by_barcode(db: DBSession, barcode: str) -> Optional[Dict[str, Any]]:
    """Return cached data for *barcode* as a plain dict, or ``None``.

    JSON columns are automatically parsed back to Python objects.
    """
    row = db.query(ProductCache).filter(ProductCache.barcode == barcode).first()
    if row is None:
        return None

    return {
        "barcode": row.barcode,
        "product_name": row.product_name or "",
        "brand": row.brand or "",
        "source": row.source or "label_photo",
        "ingredients_text": row.ingredients_text or "",
        "ingredients": _safe_json_loads(row.ingredients_json),
        "nutrition_per_serving": _safe_json_loads(row.nutrition_per_serving_json),
        "nutrition_100g": _safe_json_loads(row.nutrition_100g_json),
        "product_score": _safe_json_loads(row.product_score_json),
        "nutrition_confidence": row.nutrition_confidence or "low",
        "extraction_confidence": row.extraction_confidence or 0.0,
        "schema_version": row.schema_version or 1,
        "scoring_version": row.scoring_version or 1,
        "updated_at": row.updated_at,
    }


def upsert_cache_for_barcode(db: DBSession, barcode: str, payload: dict) -> None:
    """Insert or update the cache row for *barcode*.

    Accepts a flat dict whose keys match the ``ProductCache`` column names
    (with JSON-serializable sub-dicts for ``ingredients``, ``nutrition_*``,
    ``product_score``).
    """
    row = db.query(ProductCache).filter(ProductCache.barcode == barcode).first()
    if row is None:
        row = ProductCache(barcode=barcode)
        db.add(row)

    row.product_name = payload.get("product_name", "") or ""
    row.brand = payload.get("brand", "") or ""
    row.source = payload.get("source", "label_photo")

    row.ingredients_text = payload.get("ingredients_text", "") or ""
    row.ingredients_json = _safe_json_dumps(payload.get("ingredients"))
    row.nutrition_per_serving_json = _safe_json_dumps(payload.get("nutrition_per_serving"))
    row.nutrition_100g_json = _safe_json_dumps(payload.get("nutrition_100g"))
    row.product_score_json = _safe_json_dumps(payload.get("product_score"))

    row.nutrition_confidence = payload.get("nutrition_confidence", "low")
    row.extraction_confidence = float(payload.get("extraction_confidence", 0.0))

    row.schema_version = payload.get("schema_version", SCHEMA_VERSION)
    row.scoring_version = payload.get("scoring_version", SCORING_VERSION)

    db.commit()
    logger.info("Cache upserted for barcode=%s (source=%s)", barcode, row.source)


def cache_has_usable_nutrition(cache_row_dict: dict) -> bool:
    """Return True when the cached data has enough nutrition to score.

    Checks *both* per-100g and per-serving representations — if either
    has >= ``_MIN_NUTRITION_FIELDS`` numeric fields we consider it usable.
    """
    nut_100g = cache_row_dict.get("nutrition_100g") or {}
    if isinstance(nut_100g, str):
        nut_100g = _safe_json_loads(nut_100g)

    if _count_numeric_fields(nut_100g, _KEY_100G_FIELDS) >= _MIN_NUTRITION_FIELDS:
        return True

    nut_ps = cache_row_dict.get("nutrition_per_serving") or {}
    if isinstance(nut_ps, str):
        nut_ps = _safe_json_loads(nut_ps)

    if _count_numeric_fields(nut_ps, _KEY_PER_SERVING_FIELDS) >= _MIN_NUTRITION_FIELDS:
        return True

    return False
