"""Deterministic rules engine ."""

from __future__ import annotations
from typing import List, Dict

from ..schemas import Flag, IngredientItem, UserProfile, EvidenceSnippet
from .kb_service import get_kb_tags

# ── small static lists for diet conflicts ──────────────────────────
ANIMAL_DERIVED_TAGS = {"non-vegan", "animal-derived", "dairy", "allergen-milk", "allergen-egg"}
NON_VEGETARIAN_TAGS = {"non-vegetarian", "allergen-fish", "allergen-shellfish"}
NON_HALAL_TAGS = {"non-halal-unless-certified"}

CAFFEINE_SOURCE_TAGS = {"caffeine-source", "stimulant"}
UMBRELLA_TERM_TAGS  = {"umbrella-term"}

# Quick lookup: allergen tag prefixes -> human label
ALLERGEN_TAG_MAP = {
    "allergen-milk": "milk",
    "allergen-egg": "egg",
    "allergen-peanuts": "peanuts",
    "allergen-tree-nuts": "tree nuts",
    "allergen-soy": "soy",
    "allergen-wheat": "wheat",
    "allergen-fish": "fish",
    "allergen-shellfish": "shellfish",
}


def run_rules(
    ingredients: List[IngredientItem],
    profile: UserProfile,
    evidence: List[EvidenceSnippet],
) -> List[Flag]:
    """Return deterministic flags based on user profile and detected ingredients."""
    flags: List[Flag] = []
    evidence_ids = {e.citation_id for e in evidence}

    for ing in ingredients:
        name = ing.name_canonical.lower()
        kb_tags = set(get_kb_tags(ing.name_canonical))
        all_tags = set(ing.tags) | kb_tags

        # ── 1. Allergen detection ───────────────────────────────
        for atag, label in ALLERGEN_TAG_MAP.items():
            if atag in all_tags:
                # check if user listed this allergen
                user_allergens_lower = [a.lower() for a in profile.allergies]
                if label in user_allergens_lower or any(label in ua for ua in user_allergens_lower):
                    cids = [e.citation_id for e in evidence if _name_match(ing.name_canonical, e)]
                    flags.append(Flag(
                        type="allergen",
                        severity="high",
                        message=f"Contains {label} – listed in your allergies.",
                        related_ingredients=[ing.name_canonical],
                        citation_ids=cids,
                    ))

        # also do simple string match of user allergies against ingredient name
        for allergy in profile.allergies:
            if allergy.lower() in name or name in allergy.lower():
                if not any(f.type == "allergen" and ing.name_canonical in f.related_ingredients for f in flags):
                    flags.append(Flag(
                        type="allergen",
                        severity="high",
                        message=f"'{ing.name_canonical}' matches your allergy '{allergy}'.",
                        related_ingredients=[ing.name_canonical],
                    ))

        # ── 2. Diet conflict flags ──────────────────────────────
        if profile.vegan:
            if all_tags & ANIMAL_DERIVED_TAGS:
                flags.append(Flag(
                    type="diet_conflict",
                    severity="high",
                    message=f"'{ing.name_canonical}' is animal-derived – conflicts with vegan diet.",
                    related_ingredients=[ing.name_canonical],
                ))

        if profile.vegetarian:
            if all_tags & NON_VEGETARIAN_TAGS:
                flags.append(Flag(
                    type="diet_conflict",
                    severity="high",
                    message=f"'{ing.name_canonical}' is non-vegetarian.",
                    related_ingredients=[ing.name_canonical],
                ))

        if profile.halal:
            if all_tags & NON_HALAL_TAGS:
                flags.append(Flag(
                    type="diet_conflict",
                    severity="warn",
                    message=f"'{ing.name_canonical}' may not be halal-certified.",
                    related_ingredients=[ing.name_canonical],
                ))
            # pork-derived terms
            if any(k in name for k in ("pork", "lard", "gelatin", "bacon")):
                flags.append(Flag(
                    type="diet_conflict",
                    severity="high",
                    message=f"'{ing.name_canonical}' may be pork-derived – not halal.",
                    related_ingredients=[ing.name_canonical],
                ))

        # ── 3. Caffeine warnings ────────────────────────────────
        if all_tags & CAFFEINE_SOURCE_TAGS:
            if profile.caffeine_limit_mg is not None:
                flags.append(Flag(
                    type="caffeine",
                    severity="warn",
                    message=f"'{ing.name_canonical}' is a caffeine source. Exact amount unknown – your limit is {profile.caffeine_limit_mg} mg.",
                    related_ingredients=[ing.name_canonical],
                ))
            else:
                flags.append(Flag(
                    type="caffeine",
                    severity="info",
                    message=f"'{ing.name_canonical}' is a caffeine source.",
                    related_ingredients=[ing.name_canonical],
                ))

        # ── 4. Umbrella-term warnings ───────────────────────────
        if all_tags & UMBRELLA_TERM_TAGS:
            flags.append(Flag(
                type="umbrella_term",
                severity="warn",
                message=f"'{ing.name_canonical}' is a vague/umbrella term – exact composition unknown.",
                related_ingredients=[ing.name_canonical],
            ))

        # ── 5. User avoid-terms ─────────────────────────────────
        for term in profile.avoid_terms:
            if term.lower() in name:
                flags.append(Flag(
                    type="avoid_term",
                    severity="warn",
                    message=f"'{ing.name_canonical}' matches your avoid term '{term}'.",
                    related_ingredients=[ing.name_canonical],
                ))

    # de-duplicate flags by (type, message)
    seen = set()
    unique: List[Flag] = []
    for f in flags:
        key = (f.type, f.message)
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique


def _name_match(canonical: str, ev: EvidenceSnippet) -> bool:
    return canonical.lower() in ev.snippet.lower() or canonical.lower() in ev.title.lower()
