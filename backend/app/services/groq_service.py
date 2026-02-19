"""Groq LLM service – vision extraction + structured LLM functions.

Provides:
  - extract_label_sections: vision-based label OCR + nutrition parsing
  - groq_structure_ingredients: parse raw ingredient text into structured items
  - groq_personalized_explain: generate personalized product summary
  - groq_product_chat: product-locked conversational Q&A

Uses Groq's OpenAI-compatible chat completions endpoint.
API key read from GROQ_API_KEY environment variable — never hardcoded.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
from typing import Optional

from groq import Groq

from ..schemas import (
    LabelExtraction,
    NutritionFacts,
    StructuredIngredientsResult,
    PersonalizedSummaryResult,
    ChatAnswerResult,
    IngredientItem,
    UserProfile,
    AnalysisResult,
    EvidenceSnippet,
)

logger = logging.getLogger("labellens.groq")

# ── Constants ────────────────────────────────────────────────────
GROQ_VISION_MODEL = os.getenv(
    "GROQ_VISION_MODEL",
    "meta-llama/llama-4-scout-17b-16e-instruct",
)
GROQ_TEXT_MODEL = os.getenv(
    "GROQ_TEXT_MODEL",
    "llama-3.3-70b-versatile",
)

# Groq has a base64 payload size limit; resize if image exceeds this
_MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4 MB

# ── Prompt ───────────────────────────────────────────────────────
_EXTRACTION_PROMPT = """\
You are a food-label extraction assistant. You will be shown a photo of a \
food product label. Extract ONLY what is visible. Do not infer or guess \
values that are not clearly printed on the label.

Return ONLY valid JSON matching this exact schema (no markdown, no explanation):

{
  "ingredients_text": "<full ingredients list as printed, preserving order, or null if not visible>",
  "ingredients_confidence": <0.0-1.0>,
  "nutrition": {
    "serving_size_text": "<e.g. '1 can (355ml)' or null>",
    "serving_size_value": <numeric value or null>,
    "serving_size_unit": "<g|ml|oz|etc or null>",
    "servings_per_container": <number or null>,
    "calories": <number or null>,
    "total_fat_g": <number or null>,
    "saturated_fat_g": <number or null>,
    "trans_fat_g": <number or null>,
    "cholesterol_mg": <number or null>,
    "sodium_mg": <number or null>,
    "total_carbs_g": <number or null>,
    "fiber_g": <number or null>,
    "total_sugars_g": <number or null>,
    "added_sugars_g": <number or null>,
    "protein_g": <number or null>,
    "is_per_serving": true,
    "notes": [],
    "confidence": <0.0-1.0>
  },
  "nutrition_confidence": <0.0-1.0>,
  "missing_sections": [],
  "overall_confidence": <0.0-1.0>
}

Rules:
- If the ingredients section is not visible or not legible, set \
"ingredients_text" to null and add "ingredients" to "missing_sections".
- If the nutrition facts panel is not visible or not legible, set \
"nutrition" to null and add "nutrition" to "missing_sections".
- Preserve ingredient ordering exactly as printed on the label.
- If Nutrition Facts shows per-serving values, capture per serving and set \
"is_per_serving" to true.
- Set confidence values between 0.0 and 1.0 based on legibility.
- Return ONLY the JSON object, nothing else.
"""


# ── Client singleton ─────────────────────────────────────────────
_groq_client: Optional[Groq] = None


def _get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable is not set.")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


# ── Image helpers ────────────────────────────────────────────────
def _compress_image_if_needed(image_bytes: bytes) -> bytes:
    """Resize / compress image if it exceeds the base64 size limit."""
    if len(image_bytes) <= _MAX_IMAGE_BYTES:
        return image_bytes

    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        # Resize to max 1600px on longest side
        max_dim = 1600
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        fmt = "JPEG"
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        img.save(buf, format=fmt, quality=80)
        compressed = buf.getvalue()
        logger.info(
            "Compressed image from %d bytes to %d bytes",
            len(image_bytes),
            len(compressed),
        )
        return compressed
    except ImportError:
        logger.warning("Pillow not available for image compression")
        return image_bytes


def _to_data_url(image_bytes: bytes) -> str:
    """Convert raw image bytes to a base64 data URL."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


# ── Main extraction function ────────────────────────────────────
def extract_label_sections(image_bytes: bytes) -> LabelExtraction:
    """Extract ingredients text and nutrition facts from a label photo.

    Uses Groq vision API with JSON mode for structured output.
    Returns a LabelExtraction with confidence scores and missing-section flags.
    """
    try:
        image_bytes = _compress_image_if_needed(image_bytes)
        data_url = _to_data_url(image_bytes)

        client = _get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _EXTRACTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2048,
        )

        raw_text = response.choices[0].message.content or ""
        logger.info(
            "Groq vision response length: %d chars (model: %s)",
            len(raw_text),
            GROQ_VISION_MODEL,
        )

        parsed = json.loads(raw_text)
        return _parse_extraction(parsed)

    except json.JSONDecodeError as exc:
        logger.error("Groq vision returned invalid JSON: %s", exc)
        return _fallback_extraction("JSON parse error")
    except Exception as exc:
        logger.error("Groq vision extraction failed: %s", exc)
        return _fallback_extraction(str(exc))


def _parse_extraction(data: dict) -> LabelExtraction:
    """Parse Groq JSON response into LabelExtraction, tolerating missing keys."""
    nutrition_data = data.get("nutrition")
    nutrition_obj = None
    if nutrition_data and isinstance(nutrition_data, dict):
        try:
            nutrition_obj = NutritionFacts(**nutrition_data)
        except Exception as exc:
            logger.warning("Failed to parse nutrition from Groq response: %s", exc)

    missing = data.get("missing_sections", [])
    if not isinstance(missing, list):
        missing = []

    return LabelExtraction(
        ingredients_text=data.get("ingredients_text"),
        ingredients_confidence=float(data.get("ingredients_confidence", 0.0)),
        nutrition=nutrition_obj,
        nutrition_confidence=float(data.get("nutrition_confidence", 0.0)),
        missing_sections=missing,
        overall_confidence=float(data.get("overall_confidence", 0.0)),
    )


def _fallback_extraction(reason: str) -> LabelExtraction:
    """Return a low-confidence extraction when the API call fails."""
    return LabelExtraction(
        ingredients_text=None,
        ingredients_confidence=0.0,
        nutrition=None,
        nutrition_confidence=0.0,
        missing_sections=["ingredients", "nutrition"],
        overall_confidence=0.0,
    )


# ── Generic JSON helper ──────────────────────────────────────────
def _call_groq_json(prompt: str, temperature: float = 0.1) -> dict:
    """Call Groq text model with JSON mode and return parsed dict."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_TEXT_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that outputs valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Groq returned empty response.")
    return json.loads(content)


# ── 1. Structure raw ingredients text ─────────────────────────────
async def groq_structure_ingredients(
    ingredients_raw_text: str,
) -> StructuredIngredientsResult:
    """Parse raw ingredients text into structured items via Groq."""

    prompt = f"""You are a food-science expert. Parse the following raw ingredient list into structured data.

For each ingredient:
- name_raw: the exact text from the list
- name_canonical: a normalized English name (lowercase, singular)
- confidence: 0.0-1.0 how sure you are of the identification
- tags: relevant tags like "sweetener", "preservative", "allergen-milk", "animal-derived", "non-vegan", "caffeine-source", "umbrella-term", etc.
- notes: any brief clarification (optional)

Also identify:
- umbrella_terms: vague terms like "natural flavors", "spices", "artificial colors"
- allergen_statements: any "contains" or "may contain" allergen declarations

Raw ingredient text:
\"\"\"
{ingredients_raw_text}
\"\"\"

Return valid JSON with this structure:
{{
  "ingredients": [{{"name_raw": "...", "name_canonical": "...", "confidence": 0.9, "tags": [], "notes": ""}}],
  "umbrella_terms": [],
  "allergen_statements": []
}}"""

    parsed = _call_groq_json(prompt, temperature=0.1)
    return StructuredIngredientsResult(**parsed)


# ── 2. Personalized explanation / summary ─────────────────────────
async def groq_personalized_explain(
    user_profile: UserProfile,
    analysis: AnalysisResult,
    evidence: list[EvidenceSnippet],
) -> PersonalizedSummaryResult:
    """Generate a personalized product summary via Groq."""

    evidence_text = "\n".join(
        f"[{e.citation_id}] {e.title}: {e.snippet} ({e.source_url})"
        for e in evidence
    )
    flags_text = "\n".join(
        f"- [{f.severity.upper()}] {f.message}" for f in analysis.flags
    )
    ingredients_text = ", ".join(i.name_canonical for i in analysis.ingredients)
    profile_text = json.dumps(user_profile.model_dump(), indent=2)

    prompt = f"""You are LabelLens, a friendly food-science assistant. Write a personalized summary for this user about the product they scanned.

USER PROFILE:
{profile_text}

PRODUCT: {analysis.product.name or 'Unknown'} by {analysis.product.brand or 'Unknown'}

DETECTED INGREDIENTS: {ingredients_text}

FLAGS (from our rules engine – these are facts, do not contradict them):
{flags_text}

EVIDENCE (cite these by ID when relevant):
{evidence_text}

RULES:
- Keep it conversational but accurate.
- Reference specific ingredients and flags.
- Cite evidence using [citation_id] format.
- Include citations_used list with all citation IDs you referenced.
- Do NOT provide medical diagnoses or treatment advice.
- End with a brief takeaway.
- Maximum 300 words.
- Only discuss ingredients that are in the DETECTED INGREDIENTS list above.

Return valid JSON with this structure:
{{
  "summary": "...",
  "citations_used": ["cite_1", "cite_2"]
}}"""

    parsed = _call_groq_json(prompt, temperature=0.7)
    return PersonalizedSummaryResult(**parsed)


# ── 3. Product-locked chat ────────────────────────────────────────
async def groq_product_chat(
    session_id: str,
    message: str,
    chat_history: list[dict],
    analysis: AnalysisResult,
    evidence: list[EvidenceSnippet],
) -> ChatAnswerResult:
    """Answer a user question about the currently scanned product via Groq."""

    evidence_text = "\n".join(
        f"[{e.citation_id}] {e.title}: {e.snippet} ({e.source_url})"
        for e in evidence
    )
    ingredients_text = ", ".join(i.name_canonical for i in analysis.ingredients)
    flags_text = "\n".join(
        f"- [{f.severity.upper()}] {f.message}" for f in analysis.flags
    )
    history_text = "\n".join(
        f"{m.get('role','user').upper()}: {m.get('content','')}"
        for m in chat_history[-10:]
    )

    prompt = f"""You are LabelLens Chat, a product-locked food-science assistant.
You may ONLY answer questions about this specific product and its ingredients.

PRODUCT: {analysis.product.name or 'Unknown'} by {analysis.product.brand or 'Unknown'}
INGREDIENTS: {ingredients_text}
FLAGS: {flags_text}
EVIDENCE: {evidence_text}

CONVERSATION HISTORY:
{history_text}

USER'S NEW QUESTION: {message}

RULES:
- ONLY answer about this product and its ingredients.
- If the user asks about a different product, politely say you can only discuss the current product.
- If asked a medical question, provide educational information with disclaimer.
- Cite evidence using [citation_id] format.
- Include citations_used list.
- Do NOT fabricate ingredients not listed above.
- Maximum 250 words.

Return valid JSON with this structure:
{{
  "answer": "...",
  "citations_used": ["cite_1"]
}}"""

    parsed = _call_groq_json(prompt, temperature=0.7)
    return ChatAnswerResult(**parsed)
