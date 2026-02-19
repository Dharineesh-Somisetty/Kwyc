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
) -> tuple[int, List[str], List[str]]:
    """Return (base_score, reasons, penalties) from per-100g nutrition.

    ONE unified scoring logic for ALL products (food and beverages).
    Start at 100, compute penalties + small credits, clamp 0-100.
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
        if pen:
            score -= pen
            penalties.append(f"Energy: {energy}kcal/100g → −{pen}")

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
    if added_g is None:
        added_g = _get_serving_val(nutrition_per_serving, "total_sugars_g")
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
    """Compute a product score 0-100 with grade A/B/C/D/F.

    Scoring priority:
      1. per-100g nutrition (``nutrition`` dict) — Nutri-Score-style tiers
      2. per-serving nutrition (``nutrition_per_serving``) — DV%-based
      3. ingredient-only fallback — conservative caps apply

    ``nutrition_used`` is True when either (1) or (2) provides enough data.
    Ingredient-only ceiling (≤70, no 'A') only applies when both are missing.
    """
    ingredients = ingredients or ingredients_detected or []
    product_categories = product_categories or categories
    user_profile = user_profile or {}
    matched_entries = matched_entries or {}

    nutrition_confidence = "high"

    if not ingredients and not nutrition and not _has_usable_per_serving(nutrition_per_serving):
        return {
            "score": 50,
            "grade": "C",
            "reasons": ["No ingredients or nutrition data available."],
            "penalties": [],
            "uncertainties": ["Unable to score without data."],
            "personalized_conflicts": [],
            "nutrition_used": False,
            "nutrition_confidence": "low",
            "beverage_label": False,
            "beverage_reason": "",
        }

    # Beverage detection — informational label only
    is_bev, bev_reason = _is_beverage(
        product_name=product_name, categories=product_categories,
    )

    # ----- Determine nutrition_used -----
    has_100g = False
    if nutrition is not None:
        present_count = sum(
            1 for k in _KEY_NUTRITION_FIELDS
            if nutrition.get(k) is not None
        )
        has_100g = present_count >= 2

    has_per_serving = _has_usable_per_serving(nutrition_per_serving)
    nutrition_used = has_100g or has_per_serving

    # ----- Score from nutrition -----
    if has_100g:
        # Path 1: per-100g (preferred)
        assert nutrition is not None
        score, reasons, penalties = _score_from_nutrition(nutrition)
        uncertainties: List[str] = []
        nutrition_confidence = "high"

        # Bounded UPF penalty from ingredients (cap=15)
        if ingredients:
            upf_pen, upf_lines, upf_reasons = _compute_upf_penalty(
                ingredients, matched_entries, nutrition_used=True,
            )
            score = max(0, score - int(round(upf_pen)))
            penalties.extend(upf_lines)
            reasons.extend(upf_reasons)

    elif has_per_serving:
        # Path 2: per-serving DV%-based scoring
        score, reasons, penalties = _score_from_nutrition_per_serving(
            nutrition_per_serving,
        )
        uncertainties = [
            "Nutrition extracted per serving; could not normalize to "
            "per-100g because serving size is not in g/ml.",
        ]
        nutrition_confidence = "medium"

        # Bounded UPF penalty from ingredients (cap=15, nutrition IS used)
        if ingredients:
            upf_pen, upf_lines, upf_reasons = _compute_upf_penalty(
                ingredients, matched_entries, nutrition_used=True,
            )
            score = max(0, score - int(round(upf_pen)))
            penalties.extend(upf_lines)
            reasons.extend(upf_reasons)

    else:
        # Path 3: ingredient-only fallback
        nutrition_confidence = "low"
        if ingredients:
            score, reasons, penalties, uncertainties = (
                _score_from_ingredients_fallback(ingredients, matched_entries)
            )
        else:
            score = 50
            reasons = ["No ingredients or nutrition data available."]
            penalties = []
            uncertainties = ["Unable to score without data."]

    # Personalization overlay
    score, conflicts = _personalization_overlay(
        score, ingredients, user_profile, matched_entries,
    )

    # ── Ingredient-only caps (when nutrition NOT used) ──────────
    if not nutrition_used:
        _INGR_ONLY_CEILING = 70
        if score > _INGR_ONLY_CEILING:
            score = _INGR_ONLY_CEILING
        if "Nutrition facts not available" not in " ".join(uncertainties):
            uncertainties.append(
                "Nutrition facts not available; score is a conservative "
                "estimate from ingredients."
            )

    grade = _grade(score)

    # Grade cap: never award "A" without nutrition data
    if not nutrition_used and grade == "A":
        grade = "B"

    if conflicts and score == 0:
        grade = "F"

    return {
        "score": score,
        "grade": grade,
        "reasons": reasons,
        "penalties": penalties,
        "uncertainties": uncertainties,
        "personalized_conflicts": conflicts,
        "nutrition_used": nutrition_used,
        "nutrition_confidence": nutrition_confidence,
        "beverage_label": is_bev,
        "beverage_reason": bev_reason,
    }


# ---------------------------------------------------------------------------
# Backwards compatibility
# ---------------------------------------------------------------------------

def calculate_apex_score(ingredients: List[str], goal: str = "general") -> Dict[str, Any]:
    """Legacy wrapper."""
    return calculate_product_score(ingredients)
