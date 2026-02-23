"""Nutrition-first product scoring engine (Nutri-Score inspired, mapped 0-100).

Flowchart:
  Input (OFF barcode or OCR label)
    → Nutrition available? (per-100g OR per-serving)
      Yes (per-100g) → Compute nutrition score (strict Nutri-Score-like tiers)
      Yes (per-serving only) → Compute DV%-based score
      No  → Set baseline + nutrition_confidence='low'
    → Ingredients available?
      Yes → Detect UPF indicators via KB/heuristics
            (modified starch, flavors, emulsifiers…)
      No  → UPF penalty = 0 (ingredient uncertainty)
    → Position-weighted UPF penalty
        cap: 15 if nutrition present, 40 if missing
    → Personalization overlay
        allergy hard fail / avoid-terms penalties
    → Final score clamp 0..100, grade A/B/C/D/F
    → Return product_score + nutrition + uncertainties

Design:
1. Start at 100, subtract nutrition penalties, add small fiber/protein credits
   (never exceed 100).
2. Apply bounded UPF penalty from ingredients (position-weighted, capped).
3. Personalization overlay:
   – allergy match → score = 0
   – avoid-term match → penalty
4. ONE unified scoring logic for ALL products (food and beverages).
   Beverage detection is informational only — it does NOT change penalties.
5. Per-serving DV% scoring used as fallback when per-100g is unavailable.
   Ingredient-only ceiling (≤70, no A) only applies when BOTH are missing.

References:
  - BMJ 2024 UPF umbrella review (Lane et al.)
  - Hall et al. 2019 controlled feeding trial
  - NOVA identification (Monteiro 2019)

IMPORTANT:
  Scores are subjective heuristics; treat as guidance, not medical advice.
  UPF penalties are framed as processing signals, NOT toxicity claims.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Key nutrition fields used to determine if nutrition data is sufficient
_KEY_NUTRITION_FIELDS = frozenset({
    "sugars_g_100g", "sodium_mg_100g", "energy_kcal_100g", "sat_fat_g_100g",
})

# Per-serving fields considered "usable" for DV-based scoring
_KEY_PER_SERVING_FIELDS = (
    "calories", "sodium_mg", "saturated_fat_g", "added_sugars_g",
    "total_sugars_g", "total_fat_g", "total_carbs_g", "fiber_g", "protein_g",
)

# Daily Value reference constants
DV_SODIUM_MG = 2300
DV_ADDED_SUGAR_G = 50
DV_SAT_FAT_G = 20
REF_CALORIES = 2000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NORMALIZE_RE = re.compile(r"[^a-z0-9\s]+")


def _normalize(text: str) -> str:
    t = text.lower().strip().replace("-", " ").replace("_", " ")
    t = _NORMALIZE_RE.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Beverage detection  (INFORMATIONAL ONLY — does NOT affect scoring)
# ---------------------------------------------------------------------------

_BEVERAGE_CATEGORY_ALLOW: frozenset = frozenset({
    "beverages", "soft drinks", "carbonated drinks", "sodas",
    "juices", "fruit juices", "energy drinks", "sports drinks",
    "waters", "mineral waters", "teas", "iced teas", "coffee drinks",
})

_NOT_BEVERAGE_CATEGORIES: frozenset = frozenset({
    "cereals", "breakfast cereals", "granola", "cookies", "snacks",
    "chips", "bread", "pasta", "rice", "candy", "chocolate",
    "yogurt", "cheese",
    "cereal", "snack",
})


def _is_beverage(
    product_name: Optional[str] = None,
    categories: Optional[List[str]] = None,
    nutrition: Optional[Dict[str, Any]] = None,
) -> tuple:
    """Strict beverage detection using OFF categories ONLY.

    Returns (is_beverage: bool, reason: str).
    Does NOT use nutrition heuristics or product name.
    """
    if not categories:
        return (False, "")

    cats_lower = [c.lower().strip() if isinstance(c, str) else "" for c in categories]

    for cat in cats_lower:
        for blocked in _NOT_BEVERAGE_CATEGORIES:
            if blocked in cat:
                return (False, "")

    for cat in cats_lower:
        for allowed in _BEVERAGE_CATEGORY_ALLOW:
            if allowed in cat:
                return (True, f"matched category: {cat}")

    return (False, "")


# ---------------------------------------------------------------------------
# Position weighting (for UPF penalties)
# ---------------------------------------------------------------------------

def position_weight(i: int, n: int) -> float:
    """Position weight for ingredient at 0-based index *i* in list of *n*."""
    if n <= 1:
        return 1.0
    frac = i / (n - 1)
    if frac <= 0.20:
        return 1.0
    elif frac <= 0.50:
        return 0.7
    else:
        return 0.4


# ---------------------------------------------------------------------------
# Nutrition-based scoring (primary path — strict, unified)
# ---------------------------------------------------------------------------

def _score_from_nutrition(
    nut: Dict[str, Any],
    *,
    plain_nuts: bool = False,
    plain_oil: bool = False,
    added_sugars_g_serving: Optional[float] = None,
) -> tuple[int, List[str], List[str]]:
    """Return (base_score, reasons, penalties) from per-100g nutrition.

    ONE unified scoring logic for ALL products (food and beverages).
    Start at 100, compute penalties + small credits, clamp 0-100.

    When *plain_nuts* is True, energy / sat-fat / sugar penalties are
    reduced to reflect that calorie-dense whole nuts are nutrient-dense.
    When *plain_oil* is True, energy penalty is reduced (oils are 100%
    fat and calorie-dense by nature).
    """
    score = 100.0
    reasons: List[str] = []
    penalties: List[str] = []

    # --- Sugars penalty ---
    sugars = nut.get("sugars_g_100g")
    if sugars is not None:
        if sugars > 25:
            pen = 75
        elif sugars > 15:
            pen = 65
        elif sugars > 10:
            pen = 45
        elif sugars > 5:
            pen = 25
        elif sugars > 1:
            pen = 10
        else:
            pen = 0
        # Plain nuts with no added sugars: natural sugars are expected
        if plain_nuts and (added_sugars_g_serving is None or added_sugars_g_serving == 0):
            pen = int(round(pen * 0.3))
        if pen:
            score -= pen
            penalties.append(f"Sugars: {sugars}g/100g → −{pen}")
            reasons.append(f"High sugar content ({sugars}g/100g)")

    # --- Saturated fat penalty ---
    sat_fat = nut.get("sat_fat_g_100g")
    if sat_fat is not None:
        if sat_fat > 10:
            pen = 40
        elif sat_fat > 5:
            pen = 30
        elif sat_fat > 2:
            pen = 15
        elif sat_fat > 1:
            pen = 5
        else:
            pen = 0
        # Plain nuts: reduce sat-fat penalty when ratio to total fat is
        # likely low (sat_fat <= 12 g/100 g is typical for whole nuts)
        if plain_nuts and sat_fat <= 12:
            pen = int(round(pen * 0.5))
        if pen:
            score -= pen
            penalties.append(f"Saturated fat: {sat_fat}g/100g → −{pen}")
            reasons.append(f"Saturated fat ({sat_fat}g/100g)")

    # --- Sodium penalty ---
    sodium = nut.get("sodium_mg_100g")
    if sodium is not None:
        if sodium > 800:
            pen = 35
        elif sodium > 600:
            pen = 28
        elif sodium > 400:
            pen = 20
        elif sodium > 240:
            pen = 12
        elif sodium > 120:
            pen = 5
        else:
            pen = 0
        if pen:
            score -= pen
            penalties.append(f"Sodium: {sodium}mg/100g → −{pen}")
            reasons.append(f"Sodium ({sodium}mg/100g)")

    # --- Energy penalty ---
    energy = nut.get("energy_kcal_100g")
    if energy is not None:
        if energy > 400:
            pen = 35
        elif energy > 300:
            pen = 28
        elif energy > 200:
            pen = 12
        elif energy > 100:
            pen = 5
        else:
            pen = 0
        # Plain nuts / oils: calorie density is expected; reduce energy penalty
        if plain_oil:
            pen = int(round(pen * 0.25))
        elif plain_nuts:
            pen = int(round(pen * 0.4))
        if pen:
            score -= pen
            penalties.append(f"Energy: {energy}kcal/100g → −{pen}")

    # --- Oil-specific: saturated fat ratio penalty ---
    if plain_oil:
        sat_fat_val = nut.get("sat_fat_g_100g")
        total_fat_val = nut.get("total_fat_g_100g")
        if sat_fat_val is not None and sat_fat_val > 0:
            if total_fat_val is None or total_fat_val <= 0:
                # Estimate total fat from energy for pure oils
                e = nut.get("energy_kcal_100g")
                total_fat_val = (e / 9.0) if (e and e > 0) else 100.0
            sat_ratio = sat_fat_val / total_fat_val if total_fat_val > 0 else 0
            if sat_ratio > 0.35:
                extra = 15
            elif sat_ratio > 0.20:
                extra = 8
            else:
                extra = 0
            if extra:
                score -= extra
                penalties.append(
                    f"Oil sat-fat ratio: {sat_ratio:.0%} → −{extra}"
                )
                reasons.append(
                    f"Saturated fat ratio ({sat_ratio:.0%}) is notable for an oil."
                )

    # --- Small credits (never push above 100) ---
    fiber = nut.get("fiber_g_100g")
    if fiber is not None:
        if fiber >= 10:
            credit = 10
        elif fiber >= 6:
            credit = 7
        elif fiber >= 3:
            credit = 4
        else:
            credit = 0
        if credit:
            score += credit
            reasons.append(f"Good fiber content ({fiber}g/100g, +{credit})")

    protein = nut.get("protein_g_100g")
    if protein is not None:
        if protein >= 15:
            credit = 7
        elif protein >= 10:
            credit = 5
        elif protein >= 5:
            credit = 3
        else:
            credit = 0
        if credit:
            score += credit
            reasons.append(f"Good protein content ({protein}g/100g, +{credit})")

    # --- Whole-food credit for plain nuts / oils (capped, never exceed 100) ---
    if plain_nuts:
        wf_credit = 10
        score += wf_credit
        reasons.append(
            f"Minimally processed nuts: calorie-dense; "
            f"portion size matters. (+{wf_credit})"
        )
    elif plain_oil:
        wf_credit = 5
        score += wf_credit
        reasons.append(
            f"Oil is calorie-dense; typically used in small amounts "
            f"(portion matters). (+{wf_credit})"
        )

    # Clamp 0–100
    score = max(0, min(100, score))

    return int(round(score)), reasons, penalties


# ---------------------------------------------------------------------------
# UPF indicator detection (processing signals)
# ---------------------------------------------------------------------------

_SUGAR_PROXY_TERMS = frozenset({
    "sugar", "high fructose corn syrup", "hfcs", "corn syrup",
    "glucose syrup", "dextrose", "fructose", "maltose", "sucrose",
    "invert sugar", "syrup", "honey", "agave",
})

# ---------------------------------------------------------------------------
# Honey / syrup / plain-oil category detection
# ---------------------------------------------------------------------------

_HONEY_SYRUP_TERMS = frozenset({
    "honey", "raw honey", "pure honey", "organic honey",
    "maple syrup", "pure maple syrup", "organic maple syrup",
    "agave nectar", "agave syrup",
    "cane sugar", "raw cane sugar", "molasses", "date syrup",
})

_PLAIN_OIL_TERMS = frozenset({
    "olive oil", "extra virgin olive oil", "virgin olive oil",
    "avocado oil", "coconut oil", "virgin coconut oil",
    "sesame oil", "flaxseed oil", "walnut oil", "hemp oil",
    "grapeseed oil", "sunflower oil", "safflower oil",
    "peanut oil", "canola oil",
})

_NUT_SEED_TERMS = frozenset({
    "almond", "almonds", "cashew", "cashews", "pistachio", "pistachios",
    "pecan", "pecans", "peanut", "peanuts", "walnut", "walnuts",
    "hazelnut", "hazelnuts", "macadamia", "macadamia nuts",
    "brazil nut", "brazil nuts", "pine nut", "pine nuts",
    "sunflower seed", "sunflower seeds", "pumpkin seed", "pumpkin seeds",
    "flaxseed", "flax seed", "flax seeds", "chia seed", "chia seeds",
    "sesame seed", "sesame seeds", "hemp seed", "hemp seeds",
    "mixed nuts", "nuts", "tree nuts", "dry roasted",
})


def _is_honey_syrup(
    ingredients: List[str],
    product_name: Optional[str] = None,
    matched_entries: Optional[Dict[str, Dict]] = None,
) -> bool:
    """Detect single-ingredient honey / maple syrup / natural sweeteners.

    Returns True when:
      - Primary ingredient is a honey/syrup term, AND
      - No UPF indicators in ingredient list
    """
    if not ingredients:
        # product-name fallback inference handled separately
        return False

    matched_entries = matched_entries or {}
    first_norm = _normalize(ingredients[0])

    if not any(term in first_norm for term in _HONEY_SYRUP_TERMS):
        return False

    # No UPF additives
    for ing in ingredients:
        n = _normalize(ing)
        for term_set, tag in _HEURISTIC_TERM_SETS:
            if tag == "upf_indicator_emulsifier" and any(
                fp in n for fp in _EMULSIFIER_FALSE_POSITIVES
            ):
                continue
            if any(term in n for term in term_set):
                return False
        entry = matched_entries.get(ing)
        kb_tags = (entry.get("tags") if entry else None) or []
        if any(t.startswith("upf_indicator") for t in kb_tags):
            return False

    return True


def _is_plain_oil(
    ingredients: List[str],
    product_name: Optional[str] = None,
    matched_entries: Optional[Dict[str, Dict]] = None,
) -> bool:
    """Detect minimally-processed plain oils (e.g., extra virgin olive oil).

    Returns True when:
      - Ingredients count <= 2 AND the primary is a known oil term
      - No UPF indicators
    """
    if not ingredients or len(ingredients) > 3:
        return False

    matched_entries = matched_entries or {}

    # First ingredient must be a plain oil
    first_norm = _normalize(ingredients[0])
    if not any(term in first_norm for term in _PLAIN_OIL_TERMS):
        return False

    # No UPF additives in any ingredient
    for ing in ingredients:
        n = _normalize(ing)
        for term_set, tag in _HEURISTIC_TERM_SETS:
            if tag == "upf_indicator_emulsifier" and any(
                fp in n for fp in _EMULSIFIER_FALSE_POSITIVES
            ):
                continue
            if any(term in n for term in term_set):
                return False
        entry = matched_entries.get(ing)
        kb_tags = (entry.get("tags") if entry else None) or []
        if any(t.startswith("upf_indicator") for t in kb_tags):
            return False

    return True


# ---------------------------------------------------------------------------
# Processing badge computation
# ---------------------------------------------------------------------------

def _compute_processing_badge(
    ingredients: List[str],
    matched_entries: Optional[Dict[str, Dict]] = None,
    is_honey_syrup: bool = False,
    is_plain_oil: bool = False,
    is_plain_nuts: bool = False,
) -> Dict[str, Any]:
    """Compute a processing badge separate from nutrition score.

    Returns {
        "level": "minimally_processed" | "processed" | "upf_signals",
        "signals": [list of detected UPF signal descriptions],
    }
    """
    matched_entries = matched_entries or {}
    signals: List[str] = []

    # Collect all UPF signals
    for ing in ingredients:
        entry = matched_entries.get(ing)
        kb_tags = (entry.get("tags") if entry else None) or []
        upf_tags = _detect_upf_tags(ing, kb_tags if kb_tags else None)
        for tag in upf_tags:
            desc = tag.replace("upf_indicator_", "").replace("_", " ")
            signals.append(f"{desc} (from '{ing}')")

    # Determine level
    if signals:
        level = "upf_signals"
    elif is_honey_syrup or is_plain_oil or is_plain_nuts:
        level = "minimally_processed"
    elif len(ingredients) <= 2:
        level = "minimally_processed"
    else:
        level = "processed"

    return {"level": level, "signals": signals}


# ---------------------------------------------------------------------------
# Ingredient inference fallback (for OCR failures)
# ---------------------------------------------------------------------------

_INFER_FROM_NAME: List[tuple] = [
    # (name_patterns, inferred_ingredient, category_hint)
    (_HONEY_SYRUP_TERMS, "honey", "honey_syrup"),
    (_NUT_SEED_TERMS, "mixed nuts", "nuts_seeds_plain"),
    (_PLAIN_OIL_TERMS, "olive oil", "oils_plain"),
]


def _try_infer_ingredients(
    product_name: Optional[str],
    product_categories: Optional[List[str]] = None,
) -> tuple[Optional[str], Optional[str], bool]:
    """Attempt to infer a single-ingredient from a product name or category.

    Returns (inferred_ingredient_text, category_hint, did_infer).
    Returns (None, None, False) if inference is not possible.
    """
    sources = []
    if product_name:
        sources.append(_normalize(product_name))
    for cat in (product_categories or []):
        sources.append(_normalize(str(cat)))

    for source in sources:
        for term_set, default_ing, cat_hint in _INFER_FROM_NAME:
            if any(term in source for term in term_set):
                return default_ing, cat_hint, True

    return None, None, False

# UPF indicator tag → base penalty
_UPF_BASE_PENALTIES: Dict[str, float] = {
    "upf_indicator_modified_starch":    12.0,
    "upf_indicator_flavor":             4.0,
    "upf_indicator_color":              4.0,
    "upf_indicator_emulsifier":         4.0,
    "upf_indicator_sweetener":          4.0,
    "upf_indicator_hydrogenated":       6.0,
    "upf_indicator_maltodextrin":       5.0,
    "upf_indicator_preservative":       4.0,
}

# Heuristic detection terms (fallback when KB tags are missing)
_MODIFIED_STARCH_TERMS = frozenset({
    "modified starch", "modified corn starch", "modified food starch",
    "modified maize starch", "modified tapioca starch", "modified potato starch",
    "pregelatinized starch", "pre gelatinized starch", "starch acetate",
    "acetylated starch", "acetylated distarch adipate",
    "hydroxypropyl distarch phosphate", "starch sodium octenyl succinate",
    "e1420", "e1422", "e1442", "e1450",
})

_FLAVOR_TERMS = frozenset({
    "natural flavor", "natural flavors", "artificial flavor", "artificial flavors",
    "natural and artificial flavor", "natural and artificial flavors",
    "flavoring", "flavourings",
})

_COLOR_TERMS_UPF = frozenset({
    "caramel color", "artificial color", "red 40", "yellow 5", "yellow 6",
    "blue 1", "blue 2", "red 3", "green 3", "titanium dioxide",
})

_EMULSIFIER_TERMS = frozenset({
    "lecithin", "soy lecithin", "sunflower lecithin",
    "mono and diglycerides", "mono- and diglycerides",
    "polysorbate", "polysorbate 80", "polysorbate 60",
})

# Terms that should NEVER trigger emulsifier heuristic
_EMULSIFIER_FALSE_POSITIVES = frozenset({
    "sunflower oil", "sunflower seed oil", "high oleic sunflower oil",
    "safflower oil", "canola oil", "soybean oil", "vegetable oil",
    "palm oil", "palm kernel oil", "coconut oil", "corn oil",
    "olive oil", "peanut oil", "cottonseed oil", "rapeseed oil",
})

_SWEETENER_TERMS_UPF = frozenset({
    "sucralose", "aspartame", "acesulfame potassium", "acesulfame k",
    "saccharin", "neotame", "advantame",
})

_HYDROGENATED_TERMS = frozenset({
    "hydrogenated", "partially hydrogenated", "hydrogenated oil",
    "partially hydrogenated oil", "hydrogenated vegetable oil",
    "partially hydrogenated soybean oil",
})

_MALTODEXTRIN_TERMS = frozenset({
    "maltodextrin",
})

_PRESERVATIVE_TERMS_UPF = frozenset({
    "sodium benzoate", "potassium benzoate", "potassium sorbate",
    "calcium propionate",
    "bha", "bht", "tbhq", "sodium nitrite", "sodium nitrate",
    "potassium nitrite", "potassium nitrate",
})

_HEURISTIC_TERM_SETS: List[tuple] = [
    (_MODIFIED_STARCH_TERMS, "upf_indicator_modified_starch"),
    (_FLAVOR_TERMS, "upf_indicator_flavor"),
    (_COLOR_TERMS_UPF, "upf_indicator_color"),
    (_EMULSIFIER_TERMS, "upf_indicator_emulsifier"),
    (_SWEETENER_TERMS_UPF, "upf_indicator_sweetener"),
    (_HYDROGENATED_TERMS, "upf_indicator_hydrogenated"),
    (_MALTODEXTRIN_TERMS, "upf_indicator_maltodextrin"),
    (_PRESERVATIVE_TERMS_UPF, "upf_indicator_preservative"),
]


def _detect_upf_tags(ingredient: str, kb_tags: Optional[List[str]] = None) -> List[str]:
    """Detect UPF indicator tags for an ingredient (KB first, heuristic fallback).

    Emulsifier false positives (generic oils) are filtered out.
    """
    upf_tags: List[str] = []

    if kb_tags:
        for t in kb_tags:
            if t.startswith("upf_indicator"):
                upf_tags.append(t)
        if upf_tags:
            return upf_tags

    n = _normalize(ingredient)

    # Skip emulsifier detection for generic oils
    is_oil_fp = any(fp in n for fp in _EMULSIFIER_FALSE_POSITIVES)

    for term_set, tag in _HEURISTIC_TERM_SETS:
        if tag == "upf_indicator_emulsifier" and is_oil_fp:
            continue
        for term in term_set:
            if term in n:
                upf_tags.append(tag)
                break
    return upf_tags


def _compute_upf_penalty(
    ingredients: List[str],
    matched_entries: Optional[Dict[str, Dict]],
    nutrition_used: bool,
) -> tuple[float, List[str], List[str]]:
    """Compute bounded UPF processing-signal penalty.

    When *nutrition_used* is False, penalties are multiplied by 1.75
    and the cap is raised to 40 (conservative ingredient-only mode).

    Returns (penalty_total, penalty_lines, reason_notes).
    """
    matched_entries = matched_entries or {}
    cap = 15.0 if nutrition_used else 40.0
    multiplier = 1.0 if nutrition_used else 1.75
    n = len(ingredients)

    raw_penalty = 0.0
    penalty_lines: List[str] = []
    reason_notes: List[str] = []

    for i, ing in enumerate(ingredients):
        entry = matched_entries.get(ing)
        kb_tags = (entry.get("tags") if entry else None) or []
        upf_tags = _detect_upf_tags(ing, kb_tags if kb_tags else None)

        pw = position_weight(i, n)

        for tag in upf_tags:
            base = _UPF_BASE_PENALTIES.get(tag, 3.0)
            delta = base * pw * multiplier
            # Modified starch in top 5 → extra penalty
            if tag == "upf_indicator_modified_starch" and i < 5:
                delta += 6.0 * multiplier
            raw_penalty += delta
            desc = tag.replace("upf_indicator_", "").replace("_", " ")
            penalty_lines.append(
                f"UPF signal: {desc} from '{ing}' (pos {i+1}) → −{delta:.1f}"
            )

    capped = min(raw_penalty, cap)
    if capped > 0:
        reason_notes.append(
            f"Processing signals detected (UPF penalty: −{capped:.0f}, "
            f"cap={cap:.0f})"
        )
    if raw_penalty > cap:
        penalty_lines.append(
            f"UPF penalty capped at −{cap:.0f} (raw was −{raw_penalty:.1f})"
        )

    return capped, penalty_lines, reason_notes


# ---------------------------------------------------------------------------
# Plain nuts/seeds category detection
# ---------------------------------------------------------------------------

# _NUT_SEED_TERMS is defined above (near _PLAIN_OIL_TERMS)

_SUGAR_INGREDIENT_TERMS_NUTS = frozenset({
    "sugar", "cane sugar", "brown sugar", "powdered sugar",
    "confectioners sugar", "icing sugar",
    "high fructose corn syrup", "hfcs", "corn syrup",
    "glucose syrup", "dextrose", "fructose", "maltose", "sucrose",
    "invert sugar", "syrup", "honey", "agave", "maple syrup",
    "molasses", "treacle", "caramel", "candy coating",
    "chocolate", "milk chocolate", "dark chocolate",
    "yogurt coating", "candy",
})


def _is_plain_nuts_seeds(
    ingredients: List[str],
    nutrition: Optional[Dict[str, Any]] = None,
    nutrition_per_serving: Any = None,
    matched_entries: Optional[Dict[str, Dict]] = None,
) -> bool:
    """Detect minimally processed plain nuts/seeds.

    Returns True when:
      a) Ingredients are mostly nuts/seeds (ratio >= 0.4)
      b) No added sugars and no sugar-type ingredient strings
      c) Sodium is low (<=480 mg/100 g  or  <=120 mg/serving)
      d) No UPF indicators (flavors, preservatives, emulsifiers, etc.)
    """
    if not ingredients:
        return False

    matched_entries = matched_entries or {}
    n_total = len(ingredients)

    # (a) Count nut/seed ingredients
    nut_count = sum(
        1 for ing in ingredients
        if any(term in _normalize(ing) for term in _NUT_SEED_TERMS)
    )
    if nut_count < 1 or nut_count / n_total < 0.4:
        return False

    # (b) No added sugars and no sugar-type ingredient strings
    if nutrition_per_serving is not None:
        added = _get_serving_val(nutrition_per_serving, "added_sugars_g")
        if added is not None and added > 0:
            return False

    for ing in ingredients:
        n = _normalize(ing)
        if any(term in n for term in _SUGAR_INGREDIENT_TERMS_NUTS):
            return False

    # (c) Low sodium
    if nutrition:
        sodium_100g = nutrition.get("sodium_mg_100g")
        if sodium_100g is not None and sodium_100g > 480:
            return False
    if nutrition_per_serving is not None:
        sodium_srv = _get_serving_val(nutrition_per_serving, "sodium_mg")
        if sodium_srv is not None and sodium_srv > 120:
            return False

    # (d) No UPF indicators in ingredients
    for ing in ingredients:
        n = _normalize(ing)
        for term_set, tag in _HEURISTIC_TERM_SETS:
            if tag == "upf_indicator_emulsifier" and any(
                fp in n for fp in _EMULSIFIER_FALSE_POSITIVES
            ):
                continue
            if any(term in n for term in term_set):
                return False
        entry = matched_entries.get(ing)
        kb_tags = (entry.get("tags") if entry else None) or []
        if any(t.startswith("upf_indicator") for t in kb_tags):
            return False

    return True


# ---------------------------------------------------------------------------
# Per-serving nutrition scoring (DV%-based fallback)
# ---------------------------------------------------------------------------

def _has_usable_per_serving(nutrition_per_serving: Any) -> bool:
    """Return True if per-serving nutrition has >= 2 usable numeric fields."""
    if nutrition_per_serving is None:
        return False
    obj = (
        nutrition_per_serving
        if isinstance(nutrition_per_serving, dict)
        else (
            nutrition_per_serving.__dict__
            if hasattr(nutrition_per_serving, "__dict__")
            else {}
        )
    )
    count = sum(
        1 for k in _KEY_PER_SERVING_FIELDS
        if obj.get(k) is not None
    )
    return count >= 2


def _get_serving_val(obj: Any, key: str) -> Optional[float]:
    """Safely get a numeric value from a dict or pydantic model."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _score_from_nutrition_per_serving(
    nutrition_per_serving: Any,
    *,
    plain_nuts: bool = False,
    plain_oil: bool = False,
) -> tuple[int, List[str], List[str]]:
    """Return (base_score, reasons, penalties) using DV%-based scoring.

    Used when per-100g nutrition is unavailable but per-serving exists.
    Start at 100, compute DV-based penalties + small credits, clamp 0-100.
    """
    score = 100.0
    reasons: List[str] = []
    penalties: List[str] = []

    # --- Sodium ---
    sodium_mg = _get_serving_val(nutrition_per_serving, "sodium_mg")
    if sodium_mg is not None and sodium_mg > 0:
        sodium_dv = min(100.0 * sodium_mg / DV_SODIUM_MG, 200.0)
        pen = 0.9 * sodium_dv
        if pen > 0:
            score -= pen
            penalties.append(f"Sodium: {sodium_mg:.0f}mg/serving ({sodium_dv:.0f}% DV) → −{pen:.0f}")
            if sodium_dv >= 20:
                reasons.append(f"High sodium per serving ({sodium_dv:.0f}% DV)")

    # --- Saturated fat ---
    sat_fat_g = _get_serving_val(nutrition_per_serving, "saturated_fat_g")
    if sat_fat_g is not None and sat_fat_g > 0:
        satfat_dv = min(100.0 * sat_fat_g / DV_SAT_FAT_G, 200.0)
        pen = 0.6 * satfat_dv
        if pen > 0:
            score -= pen
            penalties.append(f"Sat fat: {sat_fat_g:.1f}g/serving ({satfat_dv:.0f}% DV) → −{pen:.0f}")
            if satfat_dv >= 20:
                reasons.append(f"High saturated fat per serving ({satfat_dv:.0f}% DV)")

    # --- Added sugars (prefer added_sugars_g, fallback to total_sugars_g) ---
    added_g = _get_serving_val(nutrition_per_serving, "added_sugars_g")
    _explicit_added = added_g  # remember whether added_sugars_g was provided
    if added_g is None:
        added_g = _get_serving_val(nutrition_per_serving, "total_sugars_g")
        # Plain nuts with confirmed 0 added sugars: skip total-sugar penalty
        if plain_nuts and _explicit_added is None:
            added_g = None  # natural sugars — do not penalize
    if added_g is not None and added_g > 0:
        added_dv = min(100.0 * added_g / DV_ADDED_SUGAR_G, 200.0)
        pen = 1.0 * added_dv
        if pen > 0:
            score -= pen
            penalties.append(f"Sugars: {added_g:.0f}g/serving ({added_dv:.0f}% DV) → −{pen:.0f}")
            if added_dv >= 20:
                reasons.append(f"High sugar per serving ({added_dv:.0f}% DV)")

    # --- Calories ---
    calories = _get_serving_val(nutrition_per_serving, "calories")
    if calories is not None and calories > 0:
        cal_dv = min(100.0 * calories / REF_CALORIES, 200.0)
        pen = 0.5 * cal_dv
        # Plain nuts / oils: calorie density is expected
        if plain_oil:
            pen = pen * 0.25
        elif plain_nuts:
            pen = pen * 0.4
        if pen > 0:
            score -= pen
            penalties.append(f"Calories: {calories:.0f}/serving ({cal_dv:.0f}% DV) → −{pen:.0f}")
            if cal_dv >= 20:
                reasons.append(f"High calories per serving ({cal_dv:.0f}% DV)")

    # --- Small credits (fiber, protein) capped at 10 total ---
    total_credit = 0.0
    fiber_g = _get_serving_val(nutrition_per_serving, "fiber_g")
    if fiber_g is not None and fiber_g >= 3:
        credit = min(fiber_g * 1.0, 5.0)
        total_credit += credit
        reasons.append(f"Fiber: {fiber_g:.0f}g/serving (+{credit:.0f})")

    protein_g = _get_serving_val(nutrition_per_serving, "protein_g")
    if protein_g is not None and protein_g >= 5:
        credit = min(protein_g * 0.5, 5.0)
        total_credit += credit
        reasons.append(f"Protein: {protein_g:.0f}g/serving (+{credit:.0f})")

    total_credit = min(total_credit, 10.0)
    score += total_credit

    # --- Whole-food credit for plain nuts (capped, never exceed 100) ---
    if plain_nuts:
        wf_credit = 10
        score += wf_credit
        reasons.append(
            f"Minimally processed nuts: calorie-dense; "
            f"portion size matters. (+{wf_credit})"
        )
    elif plain_oil:
        wf_credit = 5
        score += wf_credit
        reasons.append(
            f"Minimally processed oil: calorie-dense; "
            f"portion size matters. (+{wf_credit})"
        )

    # Clamp 0–100
    score = max(0, min(100, score))
    return int(round(score)), reasons, penalties


# ---------------------------------------------------------------------------
# Ingredient-only fallback scoring (when nutrition is missing)
# ---------------------------------------------------------------------------

def _score_from_ingredients_fallback(
    ingredients: List[str],
    matched_entries: Optional[Dict[str, Dict]] = None,
) -> tuple[int, List[str], List[str], List[str]]:
    """Return (score, reasons, penalties, uncertainties).

    Used when nutrition data is missing. Starts at 100 and only decreases.
    """
    matched_entries = matched_entries or {}

    score = 100.0
    reasons: List[str] = []
    penalties: List[str] = []
    uncertainties: List[str] = [
        "Nutrition facts missing; score estimated from ingredient list "
        "(lower confidence)."
    ]

    # Sugar proxy: sugar-type in first 3 → flat -25
    for ing in ingredients[:3]:
        n = _normalize(ing)
        if any(t in n for t in _SUGAR_PROXY_TERMS):
            score -= 25
            reasons.append(
                "Sugar-type ingredient in top 3 — likely very high sugar product."
            )
            penalties.append("Sugar proxy (top-3 ingredient) → −25")
            break

    # UPF penalties (stronger when nutrition missing)
    upf_pen, upf_lines, upf_reasons = _compute_upf_penalty(
        ingredients, matched_entries, nutrition_used=False,
    )
    score -= upf_pen
    penalties.extend(upf_lines)
    reasons.extend(upf_reasons)

    score = max(0, min(100, score))
    return int(round(score)), reasons, penalties, uncertainties


# ---------------------------------------------------------------------------
# Personalization overlay
# ---------------------------------------------------------------------------

def _personalization_overlay(
    score: int,
    ingredients: List[str],
    user_profile: Dict[str, Any],
    matched_entries: Optional[Dict[str, Dict]],
) -> tuple[int, List[str]]:
    """Apply allergy / avoid-term penalties. Returns (adjusted_score, conflicts)."""
    conflicts: List[str] = []
    matched_entries = matched_entries or {}

    allergies = [a.strip().lower() for a in (user_profile.get("allergies") or []) if a]

    avoid_raw = user_profile.get("avoid_terms") or user_profile.get("avoidTerms") or []
    avoid_terms = [t.strip().lower() for t in avoid_raw if t]

    for idx, ing in enumerate(ingredients):
        ing_norm = _normalize(ing)
        entry = matched_entries.get(ing)
        tags = (entry.get("tags") if entry else None) or []

        for allergy in allergies:
            if allergy in ing_norm or ing_norm in allergy:
                conflicts.append(f"Allergy: '{allergy}' matches ingredient '{ing}'.")
                return 0, conflicts
            for t in tags:
                if t.startswith("allergen-"):
                    tag_allergen = t.replace("allergen-", "")
                    if tag_allergen in allergy or allergy in tag_allergen:
                        conflicts.append(f"Allergy: '{allergy}' matches tag '{t}' on '{ing}'.")
                        return 0, conflicts

        for term in avoid_terms:
            if term in ing_norm:
                penalty = 25 if idx < 5 else 15
                score = max(0, score - penalty)
                conflicts.append(f"Avoid-term: '{term}' found in '{ing}' → −{penalty}")

    return score, conflicts


# ---------------------------------------------------------------------------
# Processing analysis (new two-part system)
# ---------------------------------------------------------------------------

# Per-signal penalties for processing_score computation
_PROCESSING_SIGNAL_PENALTIES: Dict[str, float] = {
    "upf_indicator_modified_starch": 12.0,
    "upf_indicator_sweetener":       12.0,
    "upf_indicator_color":            8.0,
    "upf_indicator_preservative":     5.0,
    "upf_indicator_flavor":           4.0,
    "upf_indicator_emulsifier":       4.0,
    "upf_indicator_hydrogenated":    15.0,
    "upf_indicator_maltodextrin":     6.0,
}

_PRESERVATIVE_PENALTY_CAP = 15.0
_UMBRELLA_PENALTY_CAP = 8.0


def detect_upf_signals(
    ingredients: List[str],
    matched_entries: Optional[Dict[str, Dict]] = None,
) -> tuple[List[str], List[str], List[str]]:
    """Detect UPF processing signals from ingredients.

    Returns (signals, details, signal_tags).
    - signals: human-readable signal descriptions
    - details: detailed lines about each detection
    - signal_tags: raw tag strings for processing_score computation
    """
    matched_entries = matched_entries or {}
    signals: List[str] = []
    details: List[str] = []
    signal_tags: List[str] = []

    for i, ing in enumerate(ingredients):
        entry = matched_entries.get(ing)
        kb_tags = (entry.get("tags") if entry else None) or []
        upf_tags = _detect_upf_tags(ing, kb_tags if kb_tags else None)

        for tag in upf_tags:
            desc = tag.replace("upf_indicator_", "").replace("_", " ")
            signals.append(f"{desc} (from '{ing}')")
            details.append(
                f"UPF signal: {desc} in '{ing}' (position {i + 1})"
            )
            signal_tags.append(tag)

    return signals, details, signal_tags


def _has_hydrogenated_oil(ingredients: List[str]) -> bool:
    """Return True if any ingredient mentions hydrogenated/partially hydrogenated."""
    for ing in ingredients:
        n = _normalize(ing)
        if "hydrogenated" in n:
            return True
    return False


def _determine_processing_level(
    signals: List[str],
    ingredients: List[str],
    is_honey_syrup: bool = False,
    is_plain_oil: bool = False,
    is_plain_nuts: bool = False,
) -> str:
    """Determine processing level from signals and category flags."""
    if signals:
        return "upf_signals"
    if is_honey_syrup or is_plain_oil or is_plain_nuts:
        return "minimally_processed"
    if len(ingredients) <= 2:
        return "minimally_processed"
    return "processed"


def _compute_processing_score(level: str, signal_tags: List[str]) -> int:
    """Compute processing score 0-100 from processing level and signal tags.

    Mapping:
    - minimally_processed => 90
    - processed => 70
    - upf_signals => start at 55, subtract per-signal penalties (capped)
    """
    if level == "minimally_processed":
        return 90
    if level == "processed":
        return 70

    # upf_signals: start at 55 and subtract
    score = 55.0
    preservative_total = 0.0
    umbrella_total = 0.0

    for tag in signal_tags:
        if tag == "upf_indicator_preservative":
            pen = _PROCESSING_SIGNAL_PENALTIES.get(tag, 3.0)
            remaining = max(0.0, _PRESERVATIVE_PENALTY_CAP - preservative_total)
            actual = min(pen, remaining)
            preservative_total += actual
            score -= actual
        elif tag == "upf_indicator_flavor":
            pen = _PROCESSING_SIGNAL_PENALTIES.get(tag, 3.0)
            remaining = max(0.0, _UMBRELLA_PENALTY_CAP - umbrella_total)
            actual = min(pen, remaining)
            umbrella_total += actual
            score -= actual
        else:
            pen = _PROCESSING_SIGNAL_PENALTIES.get(tag, 3.0)
            score -= pen

    return max(0, min(100, int(round(score))))


# ---------------------------------------------------------------------------
# Portion-sensitive category detection
# ---------------------------------------------------------------------------

_NUT_BUTTER_TERMS = frozenset({
    "peanut butter", "almond butter", "cashew butter",
    "sunflower seed butter", "sun butter", "hazelnut butter",
    "walnut butter", "tahini",
})


def detect_portion_sensitive(
    ingredients: List[str],
    product_name: Optional[str] = None,
    nutrition_per_serving: Any = None,
    *,
    is_honey_syrup: bool = False,
    is_plain_oil: bool = False,
    is_plain_nuts: bool = False,
) -> Dict[str, Any]:
    """Detect whether a product is portion-sensitive and return a PortionInfo dict.

    A product is portion-sensitive when it is naturally calorie/sugar dense
    per 100g but is typically consumed in small servings.

    Returns dict with keys: portion_sensitive, typical_serving_text, note.
    """
    portion_sensitive = False
    note: Optional[str] = None
    typical_serving_text: Optional[str] = None

    # Extract serving text from nutrition_per_serving if available
    if nutrition_per_serving is not None:
        srv_text = _get_serving_val(nutrition_per_serving, "serving_size_text")
        if srv_text:
            typical_serving_text = srv_text

    norms = [_normalize(i) for i in ingredients] if ingredients else []

    # Rule 1: Single-ingredient sweetener (honey, maple syrup, agave)
    if is_honey_syrup:
        portion_sensitive = True
        note = "High sugar density; typically used in small amounts."

    # Rule 2: Single-ingredient oil
    elif is_plain_oil:
        portion_sensitive = True
        note = "Calorie dense; typically used in small amounts."

    # Rule 3: Plain nuts/seeds
    elif is_plain_nuts:
        portion_sensitive = True
        note = "Calorie dense; portion size matters."

    # Rule 4: Nut butter
    elif not portion_sensitive:
        for n in norms:
            if any(term in n for term in _NUT_BUTTER_TERMS):
                portion_sensitive = True
                note = "Calorie dense; portion size matters."
                break
        if not portion_sensitive and len(ingredients) <= 3:
            # Nuts + salt only → nut butter style
            nut_count = sum(1 for n in norms if any(t in n for t in _NUT_SEED_TERMS))
            other = [n for n in norms if not any(t in n for t in _NUT_SEED_TERMS) and n != "salt" and n != "sea salt"]
            if nut_count >= 1 and len(other) == 0:
                portion_sensitive = True
                note = "Calorie dense; portion size matters."

    # Rule 5: Small serving size (<=30g or ml)
    if not portion_sensitive and nutrition_per_serving is not None:
        srv_val = _get_serving_val(nutrition_per_serving, "serving_size_value")
        srv_unit = _get_serving_val(nutrition_per_serving, "serving_size_unit")
        if srv_val is not None and srv_unit is not None:
            if str(srv_unit).lower().strip() in ("g", "ml") and srv_val <= 30:
                portion_sensitive = True
                note = note or "Small typical serving size; portion size matters."

    # Product name fallback for portion sensitivity
    if not portion_sensitive and product_name:
        pn = _normalize(product_name)
        if any(t in pn for t in _HONEY_SYRUP_TERMS):
            portion_sensitive = True
            note = "High sugar density; typically used in small amounts."
        elif any(t in pn for t in _PLAIN_OIL_TERMS):
            portion_sensitive = True
            note = "Calorie dense; typically used in small amounts."
        elif any(t in pn for t in _NUT_BUTTER_TERMS):
            portion_sensitive = True
            note = "Calorie dense; portion size matters."

    return {
        "portion_sensitive": portion_sensitive,
        "typical_serving_text": typical_serving_text,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_product_score(
    ingredients: Optional[List[str]] = None,
    matched_entries: Optional[Dict[str, Dict]] = None,
    user_profile: Optional[Dict[str, Any]] = None,
    nutrition: Optional[Dict[str, Any]] = None,
    nutrition_per_serving: Any = None,
    product_name: Optional[str] = None,
    product_categories: Optional[List[str]] = None,
    # Aliases for flexible calling
    ingredients_detected: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Two-part scoring: nutrition_score + processing_score → final_score.

    final_score = round(0.7 * nutrition_score + 0.3 * processing_score)

    Scoring priority for nutrition_score:
      1. per-100g nutrition — Nutri-Score-style tiers
      2. per-serving nutrition — DV%-based
      3. ingredient-only fallback — conservative caps apply

    Processing_score is derived from UPF signal detection.
    Personalization (allergies, avoid terms) only affects final_score.
    """
    ingredients = ingredients or ingredients_detected or []
    product_categories = product_categories or categories
    user_profile = user_profile or {}
    matched_entries = matched_entries or {}

    nutrition_confidence = "high"

    # ── No-data early return ──────────────────────────────────
    if not ingredients and not nutrition and not _has_usable_per_serving(nutrition_per_serving):
        _empty_nut = {
            "score": 50, "grade": "C",
            "reasons": ["No ingredients or nutrition data available."],
            "penalties": [], "uncertainties": ["Unable to score without data."],
            "nutrition_used": False, "nutrition_confidence": "low",
        }
        _empty_proc = {
            "level": "processed", "processing_score": 70,
            "signals": [], "details": [],
        }
        _empty_final_val = round(0.7 * 50 + 0.3 * 70)
        return {
            "score": _empty_final_val,
            "grade": _grade(_empty_final_val),
            "reasons": ["No ingredients or nutrition data available."],
            "penalties": [],
            "uncertainties": ["Unable to score without data."],
            "personalized_conflicts": [],
            "nutrition_used": False,
            "nutrition_confidence": "low",
            "beverage_label": False,
            "beverage_reason": "",
            "nutrition_score": _empty_nut,
            "processing": _empty_proc,
            "final_score": {
                "score": _empty_final_val,
                "grade": _grade(_empty_final_val),
                "reasons": ["No ingredients or nutrition data available."],
                "uncertainties": ["Unable to score without data."],
            },
            "category": None,
            "ingredients_inferred": False,
            "nutrition_score_100g": None,
            "nutrition_score_serving": None,
            "primary_nutrition_view": "100g",
            "portion_info": {
                "portion_sensitive": False,
                "typical_serving_text": None,
                "note": None,
            },
        }

    # ── Ingredient inference fallback (OCR failure) ──────────────
    ingredients_inferred = False
    inferred_category_hint: Optional[str] = None
    if not ingredients:
        inf_text, cat_hint, did_infer = _try_infer_ingredients(
            product_name, product_categories,
        )
        if did_infer and inf_text:
            ingredients = [inf_text]
            ingredients_inferred = True
            inferred_category_hint = cat_hint

    # Beverage detection — informational label only
    is_bev, bev_reason = _is_beverage(
        product_name=product_name, categories=product_categories,
    )

    # ── Category detectors ──────────────────────────────────────
    is_plain_nuts = _is_plain_nuts_seeds(
        ingredients,
        nutrition=nutrition,
        nutrition_per_serving=nutrition_per_serving,
        matched_entries=matched_entries,
    )
    is_honey = _is_honey_syrup(
        ingredients,
        product_name=product_name,
        matched_entries=matched_entries,
    )
    is_oil = _is_plain_oil(
        ingredients,
        product_name=product_name,
        matched_entries=matched_entries,
    )

    # Inferred category hint override
    if ingredients_inferred and inferred_category_hint:
        if inferred_category_hint == "honey_syrup":
            is_honey = True
        elif inferred_category_hint == "nuts_seeds_plain":
            is_plain_nuts = True
        elif inferred_category_hint == "oils_plain":
            is_oil = True

    # Resolve added_sugars from per-serving for the per-100g scorer
    _added_sugars_srv: Optional[float] = None
    if nutrition_per_serving is not None:
        _added_sugars_srv = _get_serving_val(nutrition_per_serving, "added_sugars_g")

    # ── Determine nutrition_used ─────────────────────────────
    has_100g = False
    if nutrition is not None:
        present_count = sum(
            1 for k in _KEY_NUTRITION_FIELDS
            if nutrition.get(k) is not None
        )
        has_100g = present_count >= 2

    has_per_serving = _has_usable_per_serving(nutrition_per_serving)
    nutrition_used = has_100g or has_per_serving

    # ══════════════════════════════════════════════════════════
    # PART 1 — NUTRITION SCORE (no UPF penalties here)
    # ══════════════════════════════════════════════════════════
    if has_100g:
        assert nutrition is not None
        nut_score, nut_reasons, nut_penalties = _score_from_nutrition(
            nutrition,
            plain_nuts=is_plain_nuts,
            plain_oil=is_oil,
            added_sugars_g_serving=_added_sugars_srv,
        )
        nut_uncertainties: List[str] = []
        nutrition_confidence = "high"

    elif has_per_serving:
        nut_score, nut_reasons, nut_penalties = _score_from_nutrition_per_serving(
            nutrition_per_serving,
            plain_nuts=is_plain_nuts,
            plain_oil=is_oil,
        )
        nut_uncertainties = [
            "Nutrition extracted per serving; could not normalize to "
            "per-100g because serving size is not in g/ml.",
        ]
        nutrition_confidence = "medium"

    else:
        nutrition_confidence = "low"
        if ingredients:
            nut_score, nut_reasons, nut_penalties, nut_uncertainties = (
                _score_from_ingredients_fallback(ingredients, matched_entries)
            )
        else:
            nut_score = 50
            nut_reasons = ["No ingredients or nutrition data available."]
            nut_penalties = []
            nut_uncertainties = ["Unable to score without data."]

    # Nutrition-only ceiling (ingredient-only path)
    if not nutrition_used:
        _INGR_ONLY_CEILING = 70
        if nut_score > _INGR_ONLY_CEILING:
            nut_score = _INGR_ONLY_CEILING
        if "Nutrition facts not available" not in " ".join(nut_uncertainties):
            nut_uncertainties.append(
                "Nutrition facts not available; score is a conservative "
                "estimate from ingredients."
            )

    nut_grade = _grade(nut_score)
    if not nutrition_used and nut_grade == "A":
        nut_grade = "B"

    # ══════════════════════════════════════════════════════════
    # PART 1b — DUAL SCORING (per-100g + per-serving)
    # ══════════════════════════════════════════════════════════
    nutrition_score_100g_obj: Optional[Dict[str, Any]] = None
    nutrition_score_serving_obj: Optional[Dict[str, Any]] = None

    # Compute per-100g score if we have per-100g data
    if has_100g and nutrition is not None:
        s100, r100, p100 = _score_from_nutrition(
            nutrition,
            plain_nuts=is_plain_nuts,
            plain_oil=is_oil,
            added_sugars_g_serving=_added_sugars_srv,
        )
        g100 = _grade(s100)
        nutrition_score_100g_obj = {
            "score": s100, "grade": g100,
            "reasons": r100, "penalties": p100,
            "uncertainties": [],
            "nutrition_used": True,
            "nutrition_confidence": "high",
            "basis": "100g",
        }

    # Compute per-serving score if we have per-serving data
    if has_per_serving:
        s_srv, r_srv, p_srv = _score_from_nutrition_per_serving(
            nutrition_per_serving,
            plain_nuts=is_plain_nuts,
            plain_oil=is_oil,
        )
        g_srv = _grade(s_srv)
        srv_uncertainties: List[str] = []
        srv_confidence = "medium"
        if has_100g:
            srv_confidence = "high"
        if not has_100g:
            srv_uncertainties.append(
                "Nutrition extracted per serving; per-100g normalization "
                "not available."
            )
        nutrition_score_serving_obj = {
            "score": s_srv, "grade": g_srv,
            "reasons": r_srv, "penalties": p_srv,
            "uncertainties": srv_uncertainties,
            "nutrition_used": True,
            "nutrition_confidence": srv_confidence,
            "basis": "serving",
        }

    # ══════════════════════════════════════════════════════════
    # PORTION-SENSITIVE detection
    # ══════════════════════════════════════════════════════════
    portion_info = detect_portion_sensitive(
        ingredients,
        product_name=product_name,
        nutrition_per_serving=nutrition_per_serving,
        is_honey_syrup=is_honey,
        is_plain_oil=is_oil,
        is_plain_nuts=is_plain_nuts,
    )

    # Decide primary_nutrition_view
    if portion_info["portion_sensitive"] and nutrition_score_serving_obj is not None:
        primary_nutrition_view = "serving"
    elif nutrition_score_100g_obj is not None:
        primary_nutrition_view = "100g"
    elif nutrition_score_serving_obj is not None:
        primary_nutrition_view = "serving"
    else:
        primary_nutrition_view = "100g"

    # Add cross-view uncertainties
    if not has_100g and has_per_serving:
        if "per-100g normalization not available" not in " ".join(nut_uncertainties):
            nut_uncertainties.append(
                "Nutrition extracted per serving; per-100g normalization "
                "not available."
            )
    if not nutrition_used:
        if "Nutrition not detected" not in " ".join(nut_uncertainties):
            nut_uncertainties.append(
                "Nutrition not detected; score estimated from ingredients."
            )

    # ══════════════════════════════════════════════════════════
    # PART 2 — PROCESSING SCORE
    # ══════════════════════════════════════════════════════════
    signals, signal_details, signal_tags = detect_upf_signals(
        ingredients, matched_entries,
    )

    # Hydrogenated oil check
    is_hydrogenated = _has_hydrogenated_oil(ingredients)
    if is_hydrogenated and "upf_indicator_hydrogenated" not in signal_tags:
        signal_tags.append("upf_indicator_hydrogenated")
        signals.append("hydrogenated oil detected")
        signal_details.append(
            "Hydrogenated or partially hydrogenated oil detected — strong UPF signal"
        )

    # For single-ingredient whole foods (honey/oil/nuts) without
    # hydrogenation, suppress UPF signals → minimally_processed
    if (is_honey or is_oil or is_plain_nuts) and not is_hydrogenated:
        signals_for_level: List[str] = []
    else:
        signals_for_level = signals

    proc_level = _determine_processing_level(
        signals_for_level, ingredients,
        is_honey_syrup=is_honey,
        is_plain_oil=is_oil,
        is_plain_nuts=is_plain_nuts,
    )

    # Compute processing_score from level + signal tags
    if (is_honey or is_oil or is_plain_nuts) and not is_hydrogenated:
        proc_score = _compute_processing_score(proc_level, [])
    else:
        proc_score = _compute_processing_score(proc_level, signal_tags)

    # ══════════════════════════════════════════════════════════
    # PART 3 — FINAL SCORE  (0.7 * nutrition + 0.3 * processing)
    # ══════════════════════════════════════════════════════════
    final_base = round(0.7 * nut_score + 0.3 * proc_score)

    # Ingredient-only ceiling also on final
    if not nutrition_used:
        final_base = min(final_base, 70)

    # Oil-specific: hydrogenated oil hard penalty on final
    oil_notes: List[str] = []
    if is_oil:
        if "Oil is calorie-dense" not in " ".join(nut_reasons):
            oil_notes.append(
                "Oil is calorie-dense; typically used in small amounts "
                "(portion matters)."
            )
    if is_hydrogenated:
        final_base = max(0, final_base - 25)
        oil_notes.append("Contains hydrogenated oil — significant health concern.")

    # ── Personalization overlay (only affects final_score) ────
    final_score, conflicts = _personalization_overlay(
        final_base, ingredients, user_profile, matched_entries,
    )

    final_grade = _grade(final_score)
    if not nutrition_used and final_grade == "A":
        final_grade = "B"
    if conflicts and final_score == 0:
        final_grade = "F"

    # ── Assemble reasons / uncertainties ──────────────────────
    all_reasons = nut_reasons + oil_notes
    all_uncertainties = list(nut_uncertainties)

    if ingredients_inferred:
        all_uncertainties.append(
            "Ingredients not detected from label; inferred from product "
            "name/category. Confidence is low."
        )

    # ── Build response ────────────────────────────────────────
    return {
        # Backward compatibility (top-level = final_score)
        "score": final_score,
        "grade": final_grade,
        "reasons": all_reasons,
        "penalties": nut_penalties,
        "uncertainties": all_uncertainties,
        "personalized_conflicts": conflicts,
        "nutrition_used": nutrition_used,
        "nutrition_confidence": nutrition_confidence,
        "beverage_label": is_bev,
        "beverage_reason": bev_reason,
        # ── Split outputs (v2) ──────────────────────────────
        "nutrition_score": {
            "score": nut_score,
            "grade": nut_grade,
            "reasons": nut_reasons,
            "penalties": nut_penalties,
            "uncertainties": nut_uncertainties,
            "nutrition_used": nutrition_used,
            "nutrition_confidence": nutrition_confidence,
        },
        "processing": {
            "level": proc_level,
            "processing_score": proc_score,
            "signals": signals,
            "details": signal_details,
        },
        # Backward compat alias
        "processing_badge": {
            "level": proc_level,
            "signals": signals,
        },
        "final_score": {
            "score": final_score,
            "grade": final_grade,
            "reasons": all_reasons + (
                [f"Personalization: {c}" for c in conflicts]
                if conflicts else []
            ),
            "uncertainties": all_uncertainties,
        },
        "category": (
            "nuts_seeds_plain" if is_plain_nuts else
            "honey_syrup" if is_honey else
            "oils_plain" if is_oil else
            None
        ),
        "ingredients_inferred": ingredients_inferred,
        # ── Portion-sensitive scoring (v3) ──────────────────
        "nutrition_score_100g": nutrition_score_100g_obj,
        "nutrition_score_serving": nutrition_score_serving_obj,
        "primary_nutrition_view": primary_nutrition_view,
        "portion_info": portion_info,
    }


# ---------------------------------------------------------------------------
# Backwards compatibility
# ---------------------------------------------------------------------------

def calculate_apex_score(ingredients: List[str], goal: str = "general") -> Dict[str, Any]:
    """Legacy wrapper."""
    return calculate_product_score(ingredients)
