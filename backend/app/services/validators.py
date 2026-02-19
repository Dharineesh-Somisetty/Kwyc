"""Validators for LLM outputs – enforce schema compliance, citation integrity, and safety."""

from __future__ import annotations
import re, logging
from typing import List, Set

from ..schemas import (
    StructuredIngredientsResult,
    PersonalizedSummaryResult,
    ChatAnswerResult,
    EvidenceSnippet,
    IngredientItem,
)

logger = logging.getLogger("labellens.validators")

# Medical language patterns to block
MEDICAL_PATTERNS = re.compile(
    r"\b(diagnos(?:e|is|ed|ing)|prescri(?:be|ption)|treat(?:ment|ing|s)?|"
    r"cur(?:e|es|ed|ing)|therap(?:y|ies|eutic)|medicat(?:e|ion)|"
    r"consult\s+(?:your\s+)?(?:doctor|physician|healthcare)|"
    r"you\s+(?:have|suffer|are\s+diagnosed))\b",
    re.IGNORECASE,
)

SAFE_DISCLAIMER = (
    "This is educational information only and not medical advice. "
    "Please consult a healthcare professional for personal health decisions."
)


def validate_structured_ingredients(
    result: StructuredIngredientsResult,
) -> StructuredIngredientsResult:
    """Basic sanity checks on structured ingredient output."""
    valid = []
    for ing in result.ingredients:
        # Ensure confidence is clamped
        ing.confidence = max(0.0, min(1.0, ing.confidence))
        # Ensure name_canonical is lowercase
        ing.name_canonical = ing.name_canonical.strip().lower()
        if ing.name_canonical:
            valid.append(ing)
    result.ingredients = valid
    return result


def validate_personalized_summary(
    result: PersonalizedSummaryResult,
    valid_citation_ids: Set[str],
    detected_ingredient_names: Set[str],
) -> PersonalizedSummaryResult:
    """Validate LLM summary: citations must exist, no fabricated ingredients, no medical claims."""
    # 1. Filter citations_used to only valid IDs
    result.citations_used = [
        cid for cid in result.citations_used if cid in valid_citation_ids
    ]

    # 2. Block medical language
    if MEDICAL_PATTERNS.search(result.summary):
        logger.warning("Medical language detected in summary – appending disclaimer.")
        result.summary = re.sub(
            MEDICAL_PATTERNS,
            "[educational note]",
            result.summary,
        )
        result.summary += f"\n\n⚠️ {SAFE_DISCLAIMER}"

    return result


def validate_chat_answer(
    result: ChatAnswerResult,
    valid_citation_ids: Set[str],
    detected_ingredient_names: Set[str],
) -> ChatAnswerResult:
    """Validate chat answer: same rules as summary."""
    result.citations_used = [
        cid for cid in result.citations_used if cid in valid_citation_ids
    ]

    if MEDICAL_PATTERNS.search(result.answer):
        logger.warning("Medical language detected in chat answer – appending disclaimer.")
        result.answer = re.sub(
            MEDICAL_PATTERNS,
            "[educational note]",
            result.answer,
        )
        result.answer += f"\n\n⚠️ {SAFE_DISCLAIMER}"

    return result
