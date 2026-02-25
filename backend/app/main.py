"""LabelLens – FastAPI application.

Endpoints:
  POST /api/scan/barcode   – barcode lookup + analysis
  POST /api/scan/label     – image upload (OCR) + analysis
  POST /api/chat           – product-locked chat
  GET  /health             – health check
"""

from __future__ import annotations

import io, json, logging, os, time, uuid
from collections import defaultdict
from typing import Optional

import pathlib
from dotenv import load_dotenv

# Resolve .env relative to this file so it works regardless of cwd
_env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session as DBSession

from .database import engine, get_db
from . import models
from .schemas import (
    BarcodeScanRequest, ChatRequest, ChatResponse,
    AnalysisResult, ProductMeta, UserProfile, EvidenceSnippet,
    ProductScore, Nutrition, NutritionFacts, LabelExtraction,
    PortionInfo, NutritionScoreInfo,
    ProfileCreate, ProfileUpdate, ProfileResponse,
)
from .auth import AuthUser, get_current_user, get_optional_user
from .services.off_service import fetch_product_from_off
from .services.groq_service import (
    extract_label_sections,
    groq_structure_ingredients,
    groq_personalized_explain,
    groq_product_chat,
)
from .services.kb_service import lookup_ingredients
from .services.rules_engine import run_rules
from .services.validators import (
    validate_structured_ingredients,
    validate_personalized_summary,
    validate_chat_answer,
)
from .services.scorer import calculate_product_score
from .services.cache_service import (
    get_cached_by_barcode,
    upsert_cache_for_barcode,
    cache_has_usable_nutrition,
    SCORING_VERSION,
    SCHEMA_VERSION,
)

# ── Create tables ────────────────────────────────────────────────
models.Base.metadata.create_all(bind=engine)

logger = logging.getLogger("labellens")
logging.basicConfig(level=logging.INFO)

# ── App ──────────────────────────────────────────────────────────
app = FastAPI(title="LabelLens API", version="2.0.0")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return real error details instead of generic 500."""
    logger.exception("Unhandled error: %s", exc)

    # Determine appropriate status code
    status_code = 500
    err_msg = str(exc)
    if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
        status_code = 429

    # Build response with CORS headers so the browser doesn't block it
    origin = request.headers.get("origin", "")
    headers: dict[str, str] = {}
    if origin in ALLOWED_ORIGINS:
        headers["access-control-allow-origin"] = origin
        headers["access-control-allow-credentials"] = "true"

    return JSONResponse(
        status_code=status_code,
        content={"detail": err_msg},
        headers=headers,
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Lightweight rate limiter (in-memory) ─────────────────────────
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
_request_log: dict[str, list[float]] = defaultdict(list)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = [t for t in _request_log[client_ip] if now - t < 60]
    _request_log[client_ip] = window
    if len(window) >= RATE_LIMIT:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again in a minute."})
    _request_log[client_ip].append(now)
    return await call_next(request)


# ── Health ───────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "LabelLens API"}


# ── Profile helpers ──────────────────────────────────────────────
def _get_entitlement(db: DBSession, user_id: str) -> models.UserEntitlement:
    """Return the user entitlement row, creating a free-tier default if missing."""
    ent = db.query(models.UserEntitlement).filter(
        models.UserEntitlement.user_id == user_id
    ).first()
    if not ent:
        ent = models.UserEntitlement(user_id=user_id, plan="free", max_profiles=1)
        db.add(ent)
        db.commit()
        db.refresh(ent)
    return ent


def _profile_to_user_profile(profile: models.Profile) -> UserProfile:
    """Convert a DB Profile row into the UserProfile schema used by the scorer."""
    diet = (profile.diet_style or "").lower()
    return UserProfile(
        vegan=diet == "vegan",
        vegetarian=diet in ("vegetarian", "vegan"),
        halal=diet == "halal",
        allergies=profile.allergies or [],
        avoid_terms=profile.avoid_terms or [],
    )


def _resolve_profile(
    db: DBSession, user_id: str | None, profile_id: str | None
) -> UserProfile | None:
    """Resolve an optional profile_id to a UserProfile.

    Returns None when no authenticated user or profile_id, letting the
    caller fall back to the inline user_profile from the request body.
    """
    if not user_id:
        return None
    if profile_id:
        p = db.query(models.Profile).filter(
            models.Profile.id == profile_id,
            models.Profile.user_id == user_id,
        ).first()
        if p:
            return _profile_to_user_profile(p)
    # Try the user's default profile
    p = db.query(models.Profile).filter(
        models.Profile.user_id == user_id,
        models.Profile.is_default == True,
    ).first()
    if p:
        return _profile_to_user_profile(p)
    return None


# ── Profile CRUD endpoints ──────────────────────────────────────
@app.get("/api/profiles", response_model=list[ProfileResponse])
def list_profiles(
    user: AuthUser = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """List all profiles for the authenticated user."""
    rows = (
        db.query(models.Profile)
        .filter(models.Profile.user_id == user.sub)
        .order_by(models.Profile.created_at)
        .all()
    )
    return [ProfileResponse.model_validate(r) for r in rows]


@app.post("/api/profiles", response_model=ProfileResponse, status_code=201)
def create_profile(
    body: ProfileCreate,
    user: AuthUser = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Create a new household profile (subject to plan limits)."""
    ent = _get_entitlement(db, user.sub)
    existing = (
        db.query(models.Profile)
        .filter(models.Profile.user_id == user.sub)
        .count()
    )
    if existing >= ent.max_profiles:
        raise HTTPException(
            403,
            f"Profile limit reached ({ent.max_profiles}). "
            "Upgrade to premium for more profiles.",
        )

    # If this is the first profile, force is_default = True
    is_default = body.is_default or (existing == 0)

    # If setting as default, clear other defaults
    if is_default:
        db.query(models.Profile).filter(
            models.Profile.user_id == user.sub,
            models.Profile.is_default == True,
        ).update({"is_default": False})

    row = models.Profile(
        user_id=user.sub,
        name=body.name,
        allergies=body.allergies,
        avoid_terms=body.avoid_terms,
        diet_style=body.diet_style,
        is_default=is_default,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ProfileResponse.model_validate(row)


@app.patch("/api/profiles/{profile_id}", response_model=ProfileResponse)
def update_profile(
    profile_id: str,
    body: ProfileUpdate,
    user: AuthUser = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Update an existing profile."""
    row = db.query(models.Profile).filter(
        models.Profile.id == profile_id,
        models.Profile.user_id == user.sub,
    ).first()
    if not row:
        raise HTTPException(404, "Profile not found.")

    update_data = body.model_dump(exclude_unset=True)

    # Handle default toggle
    if update_data.get("is_default"):
        db.query(models.Profile).filter(
            models.Profile.user_id == user.sub,
            models.Profile.is_default == True,
        ).update({"is_default": False})

    for key, val in update_data.items():
        setattr(row, key, val)
    db.commit()
    db.refresh(row)
    return ProfileResponse.model_validate(row)


@app.delete("/api/profiles/{profile_id}", status_code=204)
def delete_profile(
    profile_id: str,
    user: AuthUser = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Delete a profile."""
    row = db.query(models.Profile).filter(
        models.Profile.id == profile_id,
        models.Profile.user_id == user.sub,
    ).first()
    if not row:
        raise HTTPException(404, "Profile not found.")
    was_default = row.is_default
    db.delete(row)
    db.commit()
    # If the deleted profile was default, promote the oldest remaining
    if was_default:
        oldest = (
            db.query(models.Profile)
            .filter(models.Profile.user_id == user.sub)
            .order_by(models.Profile.created_at)
            .first()
        )
        if oldest:
            oldest.is_default = True
            db.commit()


@app.post("/api/profiles/{profile_id}/default", response_model=ProfileResponse)
def set_default_profile(
    profile_id: str,
    user: AuthUser = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Mark a profile as the default."""
    row = db.query(models.Profile).filter(
        models.Profile.id == profile_id,
        models.Profile.user_id == user.sub,
    ).first()
    if not row:
        raise HTTPException(404, "Profile not found.")
    db.query(models.Profile).filter(
        models.Profile.user_id == user.sub,
        models.Profile.is_default == True,
    ).update({"is_default": False})
    row.is_default = True
    db.commit()
    db.refresh(row)
    return ProfileResponse.model_validate(row)


# ── Helpers ──────────────────────────────────────────────────────
def _save_session(db: DBSession, result: AnalysisResult, profile: UserProfile):
    row = models.Session(
        session_id=result.session_id,
        product_json=result.product.model_dump_json(),
        analysis_json=result.model_dump_json(),
        user_profile_json=profile.model_dump_json(),
    )
    db.merge(row)
    db.commit()


def _get_session(db: DBSession, session_id: str) -> models.Session | None:
    return db.query(models.Session).filter(models.Session.session_id == session_id).first()


# ── Nutrition normalization (per-serving → per-100g) ─────────────
def nutrition_to_per_100g(
    n: NutritionFacts,
) -> tuple[dict | None, list[str]]:
    """Convert per-serving NutritionFacts to per-100g dict for the scorer.

    Returns (nutrition_dict_or_None, notes).
    Only converts if serving_size_value is present and unit is g or ml.
    Never infers missing numeric values.
    """
    notes: list[str] = []

    if n.serving_size_value is None or n.serving_size_value <= 0:
        notes.append("Serving size value missing; cannot normalize to per-100g.")
        return None, notes

    unit = (n.serving_size_unit or "").lower().strip()
    if unit not in ("g", "ml"):
        notes.append(
            f"Serving size unit is '{n.serving_size_unit}'; "
            "cannot normalize to per-100g (need g or ml)."
        )
        return None, notes

    factor = 100.0 / n.serving_size_value

    result: dict = {
        "energy_kcal_100g": round(n.calories * factor, 1) if n.calories is not None else None,
        "sugars_g_100g": round(n.total_sugars_g * factor, 1) if n.total_sugars_g is not None else None,
        "sat_fat_g_100g": round(n.saturated_fat_g * factor, 1) if n.saturated_fat_g is not None else None,
        "sodium_mg_100g": round(n.sodium_mg * factor, 1) if n.sodium_mg is not None else None,
        "fiber_g_100g": round(n.fiber_g * factor, 1) if n.fiber_g is not None else None,
        "protein_g_100g": round(n.protein_g * factor, 1) if n.protein_g is not None else None,
        "source": "label_photo",
        "uncertainties": [],
    }

    # Check if we have at least some useful data
    key_fields = [k for k in result if k not in ("source", "uncertainties") and result[k] is not None]
    if not key_fields:
        notes.append("No numeric nutrition values extracted; cannot compute per-100g.")
        return None, notes

    return result, notes


async def _run_analysis_pipeline(
    ingredients_raw_text: str,
    product: ProductMeta,
    profile: UserProfile,
    db: DBSession,
    nutrition: Optional[Nutrition] = None,
    product_categories: Optional[list[str]] = None,
    nutrition_per_serving: Optional[NutritionFacts] = None,
) -> AnalysisResult:
    """Shared pipeline: structure → KB → rules → score → summary → persist."""

    # 1. Structure ingredients via Groq
    structured = await groq_structure_ingredients(ingredients_raw_text)
    structured = validate_structured_ingredients(structured)

    # 2. KB lookup
    canonical_names = [i.name_canonical for i in structured.ingredients]
    evidence, matched_entries = lookup_ingredients(canonical_names)

    # 3. Deterministic rules
    flags = run_rules(structured.ingredients, profile, evidence)

    # 4. Build partial result (needed for summary prompt)
    result = AnalysisResult(
        product=product,
        ingredients_raw_text=ingredients_raw_text,
        ingredients=structured.ingredients,
        umbrella_terms=structured.umbrella_terms,
        allergen_statements=structured.allergen_statements,
        flags=flags,
        evidence=evidence,
        nutrition=nutrition,
        nutrition_per_serving=nutrition_per_serving,
    )

    # 5. Product score
    try:
        ingredient_names = [i.name_canonical for i in structured.ingredients]
        nut_dict = nutrition.model_dump(exclude={"source", "uncertainties"}) if nutrition else None
        # Prepare per-serving dict for scorer fallback
        per_serving_dict = (
            nutrition_per_serving.model_dump() if nutrition_per_serving else None
        )
        score_dict = calculate_product_score(
            ingredient_names,
            matched_entries=matched_entries,
            user_profile=profile.model_dump(),
            nutrition=nut_dict,
            nutrition_per_serving=per_serving_dict,
            product_name=product.name,
            product_categories=product_categories,
        )
        result.product_score = ProductScore(**score_dict)
    except Exception as exc:
        logger.error("Scoring failed: %s", exc)
        result.product_score = None

    # 6. Personalized summary via Groq
    try:
        summary_result = await groq_personalized_explain(profile, result, evidence)
        valid_ids = {e.citation_id for e in evidence}
        detected = {i.name_canonical for i in structured.ingredients}
        summary_result = validate_personalized_summary(summary_result, valid_ids, detected)
        result.personalized_summary = summary_result.summary
    except Exception as exc:
        logger.error("Groq summary failed: %s", exc)
        result.personalized_summary = "Summary unavailable – please try again."

    # 7. Persist
    _save_session(db, result, profile)

    return result


# ── POST /api/scan/barcode ───────────────────────────────────────
@app.post("/api/scan/barcode", response_model=AnalysisResult)
async def scan_barcode(
    req: BarcodeScanRequest,
    db: DBSession = Depends(get_db),
    user: AuthUser | None = Depends(get_optional_user),
):
    # Resolve profile: prefer profile_id → default profile → inline user_profile
    profile = (
        _resolve_profile(db, user.sub if user else None, req.profile_id)
        or req.user_profile
    )

    off = fetch_product_from_off(req.barcode)

    # ── Path A: OFF has product with ingredients ──────────────────
    if off and off.get("ingredients_text"):
        ingredients_text = off["ingredients_text"]
        product = ProductMeta(
            name=off.get("product_name"),
            brand=off.get("brand"),
            image_url=off.get("image_url"),
            barcode=req.barcode,
        )

        # Build Nutrition model from OFF nutriments (may be None)
        nutrition_obj: Optional[Nutrition] = None
        raw_nut = off.get("nutriments")
        has_off_nutrition = raw_nut is not None
        if has_off_nutrition:
            nutrition_obj = Nutrition(**raw_nut)

        categories = off.get("categories") or []

        # If OFF has no nutrition, check cache for OCR-extracted data
        cached_nutrition_per_serving = None
        nutrition_source = "not_detected"
        if has_off_nutrition:
            nutrition_source = "openfoodfacts"
        else:
            cached = get_cached_by_barcode(db, req.barcode)
            if cached and cache_has_usable_nutrition(cached):
                # Reuse cached per-100g nutrition
                nut_100g = cached.get("nutrition_100g") or {}
                if nut_100g and isinstance(nut_100g, dict) and any(
                    nut_100g.get(k) is not None
                    for k in ("energy_kcal_100g", "sugars_g_100g", "sat_fat_g_100g",
                              "sodium_mg_100g", "fiber_g_100g", "protein_g_100g")
                ):
                    nut_100g.setdefault("source", "cache")
                    nut_100g.setdefault("uncertainties", [])
                    nutrition_obj = Nutrition(**nut_100g)
                    nutrition_source = "cache"
                # Also pass through cached per-serving
                nut_ps = cached.get("nutrition_per_serving") or {}
                if nut_ps and isinstance(nut_ps, dict):
                    try:
                        cached_nutrition_per_serving = NutritionFacts(**nut_ps)
                    except Exception:
                        pass
                logger.info("Using cached nutrition for barcode=%s", req.barcode)

        result = await _run_analysis_pipeline(
            ingredients_text, product, profile, db,
            nutrition=nutrition_obj,
            product_categories=categories,
            nutrition_per_serving=cached_nutrition_per_serving,
        )

        # Tag nutrition provenance on the result (backward-compatible)
        if has_off_nutrition:
            result.nutrition_status = "verified_barcode"
            result.nutrition_source = "openfoodfacts"
        elif nutrition_source == "cache":
            result.nutrition_status = "extracted_photo"
            result.nutrition_source = "cache"
        else:
            result.nutrition_status = "not_detected"
            result.nutrition_source = None

        return result

    # ── Path B: OFF has no product or no ingredients — try cache ──
    cached = get_cached_by_barcode(db, req.barcode)
    if cached and cached.get("ingredients_text", "").strip():
        product = ProductMeta(
            name=cached.get("product_name") or (off or {}).get("product_name") or "Cached Product",
            brand=cached.get("brand") or (off or {}).get("brand") or "",
            image_url=(off or {}).get("image_url") or "",
            barcode=req.barcode,
        )

        nutrition_obj = None
        cached_nutrition_per_serving = None
        has_usable = cache_has_usable_nutrition(cached)

        if has_usable:
            nut_100g = cached.get("nutrition_100g") or {}
            if nut_100g and isinstance(nut_100g, dict) and any(
                nut_100g.get(k) is not None
                for k in ("energy_kcal_100g", "sugars_g_100g", "sat_fat_g_100g",
                          "sodium_mg_100g", "fiber_g_100g", "protein_g_100g")
            ):
                nut_100g.setdefault("source", "cache")
                nut_100g.setdefault("uncertainties", [])
                nutrition_obj = Nutrition(**nut_100g)

            nut_ps = cached.get("nutrition_per_serving") or {}
            if nut_ps and isinstance(nut_ps, dict):
                try:
                    cached_nutrition_per_serving = NutritionFacts(**nut_ps)
                except Exception:
                    pass

        result = await _run_analysis_pipeline(
            cached["ingredients_text"], product, profile, db,
            nutrition=nutrition_obj,
            nutrition_per_serving=cached_nutrition_per_serving,
        )

        result.nutrition_status = "extracted_photo" if has_usable else "not_detected"
        result.nutrition_source = "cache" if has_usable else None
        return result

    # ── Path C: Nothing available ────────────────────────────────
    if not off:
        raise HTTPException(404, "Product not found. Try uploading a label photo.")
    raise HTTPException(422, "Product found but no ingredients listed. Try uploading a label photo.")


# ── POST /api/scan/label ────────────────────────────────────────
@app.post("/api/scan/label", response_model=AnalysisResult)
async def scan_label(
    image: UploadFile = File(...),
    user_profile: str = Form("{}"),
    barcode: str = Form(""),
    profile_id: str = Form(""),
    db: DBSession = Depends(get_db),
    user: AuthUser | None = Depends(get_optional_user),
):
    """Accept a label image, extract ingredients + nutrition via Groq vision,
    then run the full analysis pipeline."""
    # Resolve profile: prefer profile_id → default profile → inline form data
    profile = (
        _resolve_profile(
            db, user.sub if user else None, profile_id or None
        )
        or UserProfile(**json.loads(user_profile))
    )

    # 1. Read image bytes
    img_bytes = await image.read()
    logger.info("Label image received: %d bytes", len(img_bytes))

    # 2. Extract label sections via Groq vision (OCR + parsing in one call)
    extraction = extract_label_sections(img_bytes)
    logger.info(
        "Label extraction: ingredients=%s nutrition=%s confidence=%.2f missing=%s",
        extraction.ingredients_text is not None,
        extraction.nutrition is not None,
        extraction.overall_confidence,
        extraction.missing_sections,
    )

    ingredients_text = extraction.ingredients_text or ""
    if not ingredients_text.strip():
        # Fall back to pytesseract OCR if Groq didn't find ingredients
        try:
            from PIL import Image as PILImage
            import pytesseract

            pil_img = PILImage.open(io.BytesIO(img_bytes))
            ocr_text: str = pytesseract.image_to_string(pil_img)
            if ocr_text and len(ocr_text.strip()) >= 5:
                ingredients_text = ocr_text
                logger.info("Fell back to pytesseract OCR (%d chars)", len(ocr_text))
        except Exception as exc:
            logger.warning("pytesseract fallback failed: %s", exc)

    if not ingredients_text or len(ingredients_text.strip()) < 5:
        # If we have nutrition data from the label, proceed without ingredients
        # The scorer can infer ingredients from product name/category
        if extraction.nutrition is not None:
            logger.info("No ingredients text but nutrition present; proceeding with inference")
            ingredients_text = ""
        else:
            raise HTTPException(422, "Could not extract text from image. Try a clearer photo.")

    # 3. Normalize nutrition to per-100g if available
    nutrition_100g_dict: dict | None = None
    nutrition_obj: Nutrition | None = None
    if extraction.nutrition is not None:
        nutrition_100g_dict, norm_notes = nutrition_to_per_100g(extraction.nutrition)
        if nutrition_100g_dict is not None:
            nutrition_obj = Nutrition(**nutrition_100g_dict)
            if norm_notes:
                nutrition_obj.uncertainties.extend(norm_notes)

    # 4. Run analysis pipeline (structure → KB → rules → score → summary)
    product = ProductMeta(name="Uploaded Label", barcode=barcode or None)
    result = await _run_analysis_pipeline(
        ingredients_text, product, profile, db,
        nutrition=nutrition_obj,
        nutrition_per_serving=extraction.nutrition,
    )

    # 5. Attach extraction data to response (backward-compatible additions)
    result.extraction = extraction
    result.nutrition_per_serving = extraction.nutrition
    result.nutrition_100g = nutrition_100g_dict

    # 6. Cache extraction under barcode for future barcode-only scans
    barcode = (barcode or "").strip()
    if barcode and (ingredients_text.strip() or extraction.nutrition is not None):
        try:
            score_dict = result.product_score.model_dump() if result.product_score else {}
            nut_ps_dict = extraction.nutrition.model_dump() if extraction.nutrition else {}
            upsert_cache_for_barcode(db, barcode, {
                "product_name": product.name or "",
                "brand": product.brand or "",
                "source": "label_photo",
                "ingredients_text": ingredients_text,
                "ingredients": [i.model_dump() for i in result.ingredients] if result.ingredients else [],
                "nutrition_per_serving": nut_ps_dict,
                "nutrition_100g": nutrition_100g_dict,
                "product_score": score_dict,
                "nutrition_confidence": result.product_score.nutrition_confidence if result.product_score else "low",
                "extraction_confidence": extraction.overall_confidence,
                "schema_version": SCHEMA_VERSION,
                "scoring_version": SCORING_VERSION,
            })
        except Exception as exc:
            logger.warning("Failed to cache label extraction for barcode=%s: %s", barcode, exc)

    return result


# ── POST /api/chat ──────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: DBSession = Depends(get_db)):
    session = _get_session(db, req.session_id)
    if not session:
        raise HTTPException(404, "Session not found. Scan a product first.")

    analysis = AnalysisResult(**json.loads(session.analysis_json))
    evidence = analysis.evidence

    try:
        answer = await groq_product_chat(
            req.session_id, req.message, req.chat_history, analysis, evidence,
        )
        valid_ids = {e.citation_id for e in evidence}
        detected = {i.name_canonical for i in analysis.ingredients}
        answer = validate_chat_answer(answer, valid_ids, detected)
    except Exception as exc:
        logger.error("Groq chat failed: %s", exc)
        raise HTTPException(502, f"Chat service error: {exc}")

    return ChatResponse(
        answer=answer.answer,
        citations_used=answer.citations_used,
    )
