"""Open Food Facts lookup service."""

from __future__ import annotations
import logging, requests
from typing import Optional, Dict, Any, List

logger = logging.getLogger("labellens.off")

OFF_URL = "https://world.openfoodfacts.org/api/v0/product/{barcode}.json"


def _safe_float(val: Any) -> Optional[float]:
    """Convert a value to float, returning None on failure."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _extract_nutriments(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract and normalise per-100g nutrition values from OFF product dict."""
    nut = product.get("nutriments")
    if not nut or not isinstance(nut, dict):
        return None

    uncertainties: List[str] = []

    # Energy: prefer kcal, else convert from kJ
    energy_kcal = _safe_float(nut.get("energy-kcal_100g"))
    if energy_kcal is None:
        energy_kj = _safe_float(nut.get("energy_100g")) or _safe_float(nut.get("energy-kj_100g"))
        if energy_kj is not None:
            energy_kcal = round(energy_kj / 4.184, 1)
            uncertainties.append("Energy converted from kJ to kcal.")

    sugars = _safe_float(nut.get("sugars_100g"))
    sat_fat = _safe_float(nut.get("saturated-fat_100g"))

    # Sodium: prefer sodium_100g (in g), else derive from salt
    sodium_g = _safe_float(nut.get("sodium_100g"))
    if sodium_g is not None:
        sodium_mg = round(sodium_g * 1000, 1)
    else:
        salt_g = _safe_float(nut.get("salt_100g"))
        if salt_g is not None:
            sodium_mg = round((salt_g * 1000) / 2.5, 1)
            uncertainties.append("Sodium derived from salt value (salt/2.5).")
        else:
            sodium_mg = None

    fiber = _safe_float(nut.get("fiber_100g"))
    protein = _safe_float(nut.get("proteins_100g"))

    # Only return if we have at least one meaningful value
    has_any = any(v is not None for v in [energy_kcal, sugars, sat_fat, sodium_mg, fiber, protein])
    if not has_any:
        return None

    return {
        "energy_kcal_100g": energy_kcal,
        "sugars_g_100g": sugars,
        "sat_fat_g_100g": sat_fat,
        "sodium_mg_100g": sodium_mg,
        "fiber_g_100g": fiber,
        "protein_g_100g": protein,
        "source": "openfoodfacts",
        "uncertainties": uncertainties,
    }


def _extract_categories(product: Dict[str, Any]) -> List[str]:
    """Return a cleaned list of product category tags."""
    raw = product.get("categories_tags") or product.get("categories_tags_en") or []
    cleaned: List[str] = []
    for tag in raw:
        val = tag.split(":", 1)[-1] if ":" in tag else tag
        cleaned.append(val.replace("-", " ").strip().lower())
    return cleaned


def fetch_product_from_off(barcode: str) -> Optional[Dict[str, Any]]:
    """Lookup a barcode on Open Food Facts.

    Returns dict with product_name, brand, image_url, ingredients_text,
    cleaned ingredients tag list, nutriments, and categories.
    """
    url = OFF_URL.format(barcode=barcode)
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "LabelLens/2.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("OFF request failed for %s: %s", barcode, exc)
        return None

    if data.get("status") != 1:
        return None

    product = data.get("product", {})

    # Clean ingredient tags (e.g. "en:sugar" → "sugar")
    raw_tags = product.get("ingredients_tags", [])
    clean_ingredients = []
    for tag in raw_tags:
        value = tag.split(":", 1)[-1] if ":" in tag else tag
        clean_ingredients.append(value.replace("-", " "))

    return {
        "product_name": product.get("product_name") or product.get("product_name_en", "Unknown Product"),
        "brand": product.get("brands", ""),
        "image_url": product.get("image_url", ""),
        "ingredients_text": product.get("ingredients_text") or product.get("ingredients_text_en", ""),
        "ingredients": clean_ingredients,
        "nutriments": _extract_nutriments(product),
        "categories": _extract_categories(product),
    }

