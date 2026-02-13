"""Product scoring engine (generic grocery products).

Design goals:
- Score any food/drink product using ingredient list (+ optional KB tags + user profile).
- Keep scoring deterministic and explainable (LLM can *explain* the score, but does not decide it).
- Provide a breakdown so the UI can show "why".

IMPORTANT:
- Scores are subjective heuristics; treat as guidance, not medical advice.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------
# Helpers
# -----------------------------

_NORMALIZE_RE = re.compile(r"[^a-z0-9\s]+")


def _normalize(text: str) -> str:
    t = text.lower().strip().replace("-", " ").replace("_", " ")
    t = _NORMALIZE_RE.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _decay_weight(i: int, base: float = 0.70) -> float:
    """Earlier ingredients typically appear in larger amounts."""
    return base ** i


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


# -----------------------------
# Tag weights (tunable)
# Positive values = bonuses; negative values = penalties
# -----------------------------

TAG_WEIGHTS: Dict[str, float] = {
    # Processing / additives
    "added-sugar": -14.0,
    "artificial-sweetener": -6.0,
    "sugar-alcohol": -5.0,
    "artificial-color": -5.0,
    "preservative": -3.0,
    "emulsifier": -2.0,
    "thickener": -1.5,
    "additive": -1.0,
    "umbrella-term": -3.0,

    # Ingredient types (soft signals)
    "oil": -1.5,
    "gluten": -0.5,  # not "bad"; only relevant for gluten-free users (handled separately)
    "fiber": +2.0,
    "produce": +1.0,
    "grain": +0.5,
    "legume": +0.5,
    "seed-or-nut": +0.5,
}

# Words to detect when KB coverage is missing (fallback heuristics)
UMB_TERMS = {"natural flavors", "natural flavour", "spices", "seasonings", "flavoring", "colour", "color", "artificial flavors"}
SUGAR_TERMS = {"sugar", "syrup", "dextrose", "fructose", "glucose", "maltodextrin", "honey", "molasses"}
SWEETENER_TERMS = {"sucralose", "acesulfame", "aspartame", "saccharin", "stevia", "monk fruit", "erythritol", "xylitol", "sorbitol", "maltitol"}
COLOR_TERMS = {"red 40", "yellow 5", "yellow 6", "blue 1", "blue 2", "caramel color", "titanium dioxide"}
PRESERVATIVE_TERMS = {"sodium benzoate", "potassium sorbate", "calcium propionate", "sodium nitrite", "sodium nitrate"}

CAFFEINE_TERMS = {"caffeine", "guarana", "coffee", "tea extract", "green tea", "yerba mate"}


def infer_tags_fallback(ingredient: str) -> List[str]:
    """Fallback tagging when KB is missing. Conservative, substring-based."""
    n = _normalize(ingredient)
    tags: List[str] = []

    # umbrella terms
    if any(term in n for term in ["natural flavor", "artificial flavor", "spice", "seasoning", "flavoring"]):
        tags.append("umbrella-term")

    # added sugars (broad)
    if any(term in n for term in ["sugar", "syrup", "dextrose", "fructose", "glucose", "maltodextrin", "molasses", "honey"]):
        tags.append("added-sugar")

    # sweeteners
    if any(term in n for term in ["sucralose", "acesulfame", "aspartame", "saccharin", "stevia", "monk fruit"]):
        tags.append("artificial-sweetener")
    if any(term in n for term in ["erythritol", "xylitol", "sorbitol", "maltitol", "mannitol"]):
        tags.append("sugar-alcohol")

    # colors
    if any(term in n for term in ["red 40", "yellow 5", "yellow 6", "blue 1", "blue 2", "caramel color", "titanium dioxide"]):
        tags.append("artificial-color")

    # preservatives
    if any(term in n for term in ["sodium benzoate", "potassium sorbate", "calcium propionate", "sodium nitrite", "sodium nitrate"]):
        tags.append("preservative")

    # oils
    if "oil" in n and "essential oil" not in n:
        tags.append("oil")

    return list(dict.fromkeys(tags))


def _user_allergy_hit(user_profile: Dict[str, Any], ingredient_norm: str, tags: List[str]) -> Optional[str]:
    allergies = [a.strip().lower() for a in (user_profile.get("allergies") or []) if a]
    if not allergies:
        return None
    # Simple name match
    for a in allergies:
        if a in ingredient_norm or ingredient_norm in a:
            return a
    # Tag-based match (if you store allergen tags in KB like allergen-milk, allergen-peanut)
    for t in tags:
        if t.startswith("allergen-"):
            allergen = t.replace("allergen-", "")
            if allergen in allergies:
                return allergen
    return None


def calculate_product_score(
    ingredients: List[str],
    matched_entries: Optional[Dict[str, Dict]] = None,
    user_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Score a product based on ingredients, optional KB matches, and optional user profile.

    Returns:
      {
        "score": float,
        "grade": "A|B|C|D|F",
        "reasons_good": [str],
        "reasons_bad": [str],
        "uncertainties": [str],
        "personalized_conflicts": [str],
      }
    """
    if not ingredients:
        return {
            "score": 50.0,
            "grade": "C",
            "reasons_good": [],
            "reasons_bad": ["No ingredient list provided."],
            "uncertainties": ["Unable to score without ingredients."],
            "personalized_conflicts": [],
        }

    matched_entries = matched_entries or {}
    user_profile = user_profile or {}

    score = 100.0
    uncertainties: List[str] = []
    conflicts: List[str] = []

    # track contributions for explanation
    contributions: List[Tuple[float, str]] = []

    for i, ing in enumerate(ingredients):
        ing_norm = _normalize(ing)
        entry = matched_entries.get(ing)
        tags = (entry.get("tags") if entry else None) or infer_tags_fallback(ing_norm)

        # Personalized hard constraints
        allergy_hit = _user_allergy_hit(user_profile, ing_norm, tags)
        if allergy_hit:
            conflicts.append(f"Allergy match: '{allergy_hit}' appears in ingredient '{ing}'.")
            # Hard fail for allergy conflicts
            return {
                "score": 0.0,
                "grade": "F",
                "reasons_good": [],
                "reasons_bad": ["Contains an ingredient that matches a declared allergy."],
                "uncertainties": [],
                "personalized_conflicts": conflicts,
            }

        # Diet conflicts (simple; best handled in rules engine too)
        vegan = bool(user_profile.get("vegan"))
        vegetarian = bool(user_profile.get("vegetarian"))
        halal = bool(user_profile.get("halal"))

        if vegan and ("animal-derived" in tags or "dairy" in tags):
            conflicts.append(f"Vegan preference conflict: '{ing}' may be animal-derived.")
        if vegetarian and ("animal-derived" in tags):
            conflicts.append(f"Vegetarian preference conflict: '{ing}' is animal-derived.")
        # Halal is nuanced; treat animal-derived as "needs verification"
        if halal and ("animal-derived" in tags):
            uncertainties.append(f"Halal verification needed for: '{ing}' (source/process not specified).")

        # Caffeine limit heuristics
        caffeine_limit = user_profile.get("caffeineLimitMg")
        if caffeine_limit is not None:
            if any(term in ing_norm for term in ["caffeine", "guarana", "yerba mate", "tea extract", "coffee"]):
                uncertainties.append("Caffeine present but amount (mg) may not be available from ingredients alone.")
                contributions.append((-2.0 * _decay_weight(i), f"Caffeine source detected: {ing}"))
                score -= 2.0 * _decay_weight(i)

        # Processing-related scoring via tags
        w = _decay_weight(i)
        for t in tags:
            if t in TAG_WEIGHTS:
                delta = TAG_WEIGHTS[t] * w
                score += delta
                if abs(delta) >= 0.5:
                    label = f"{t} ({'+' if delta>0 else ''}{delta:.1f}) from {ing}"
                    contributions.append((delta, label))

        # Umbrella term uncertainty
        if "umbrella-term" in tags:
            uncertainties.append(f"Umbrella term may hide specific components: '{ing}'")

    # Apply diet conflict penalty softly (rules engine should handle strict blocking)
    if conflicts:
        # small penalty per conflict, capped
        penalty = min(25.0, 6.0 * len(conflicts))
        score -= penalty
        contributions.append((-penalty, "Personal preference conflicts present"))

    # Clamp score
    score = max(0.0, min(100.0, score))

    # Build reasons: pick top deltas
    contributions_sorted = sorted(contributions, key=lambda x: x[0])
    bad = [c[1] for c in contributions_sorted[:6] if c[0] < 0]
    good = [c[1] for c in reversed(contributions_sorted[-6:]) if c[0] > 0]

    # De-duplicate uncertainties
    uncertainties = list(dict.fromkeys(uncertainties))

    return {
        "score": round(score, 1),
        "grade": _grade(score),
        "reasons_good": good,
        "reasons_bad": bad,
        "uncertainties": uncertainties,
        "personalized_conflicts": conflicts,
    }


# -----------------------------
# Backwards compatibility
# -----------------------------
def calculate_apex_score(ingredients: List[str], goal: str = "general") -> Dict[str, Any]:
    """Legacy wrapper around the new scoring engine.
    goal is ignored in the new generic scoring, but kept to avoid breaking imports.
    """
    return calculate_product_score(ingredients)
