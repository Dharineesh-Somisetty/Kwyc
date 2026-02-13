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
    ProductScore,
)
from .services.off_service import fetch_product_from_off
from .services.gemini_service import (
    gemini_structure_ingredients,
    gemini_personalized_explain,
    gemini_product_chat,
)
from .services.kb_service import lookup_ingredients
from .services.rules_engine import run_rules
from .services.validators import (
    validate_structured_ingredients,
    validate_personalized_summary,
    validate_chat_answer,
)
from .services.scorer import calculate_product_score

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


async def _run_analysis_pipeline(
    ingredients_raw_text: str,
    product: ProductMeta,
    profile: UserProfile,
    db: DBSession,
) -> AnalysisResult:
    """Shared pipeline: structure → KB → rules → summary → persist."""

    # 1. Structure ingredients via Gemini
    structured = await gemini_structure_ingredients(ingredients_raw_text)
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
    )

    # 5. Product score
    try:
        ingredient_names = [i.name_canonical for i in structured.ingredients]
        score_dict = calculate_product_score(
            ingredient_names,
            matched_entries=matched_entries,
            user_profile=profile.model_dump(),
        )
        result.product_score = ProductScore(**score_dict)
    except Exception as exc:
        logger.error("Scoring failed: %s", exc)
        result.product_score = None

    # 6. Personalized summary via Gemini
    try:
        summary_result = await gemini_personalized_explain(profile, result, evidence)
        valid_ids = {e.citation_id for e in evidence}
        detected = {i.name_canonical for i in structured.ingredients}
        summary_result = validate_personalized_summary(summary_result, valid_ids, detected)
        result.personalized_summary = summary_result.summary
    except Exception as exc:
        logger.error("Gemini summary failed: %s", exc)
        result.personalized_summary = "Summary unavailable – please try again."

    # 7. Persist
    _save_session(db, result, profile)

    return result


# ── POST /api/scan/barcode ───────────────────────────────────────
@app.post("/api/scan/barcode", response_model=AnalysisResult)
async def scan_barcode(req: BarcodeScanRequest, db: DBSession = Depends(get_db)):
    off = fetch_product_from_off(req.barcode)
    if not off:
        raise HTTPException(404, "Product not found on Open Food Facts.")

    ingredients_text = off.get("ingredients_text", "")
    if not ingredients_text:
        raise HTTPException(422, "Product found but no ingredients listed.")

    product = ProductMeta(
        name=off.get("product_name"),
        brand=off.get("brand"),
        image_url=off.get("image_url"),
        barcode=req.barcode,
    )

    result = await _run_analysis_pipeline(ingredients_text, product, req.user_profile, db)
    return result


# ── POST /api/scan/label ────────────────────────────────────────
@app.post("/api/scan/label", response_model=AnalysisResult)
async def scan_label(
    image: UploadFile = File(...),
    user_profile: str = Form("{}"),
    db: DBSession = Depends(get_db),
):
    """Accept a label image, run OCR, then analysis pipeline."""
    profile = UserProfile(**json.loads(user_profile))

    # Read image bytes
    img_bytes = await image.read()

    # OCR via pytesseract (fallback)
    try:
        from PIL import Image
        import pytesseract

        pil_img = Image.open(io.BytesIO(img_bytes))
        raw_text: str = pytesseract.image_to_string(pil_img)
    except ImportError:
        raise HTTPException(500, "OCR dependencies (pytesseract / Pillow) not installed.")
    except Exception as exc:
        raise HTTPException(422, f"OCR failed: {exc}")

    if not raw_text or len(raw_text.strip()) < 5:
        raise HTTPException(422, "Could not extract text from image. Try a clearer photo.")

    product = ProductMeta(name="Uploaded Label")
    result = await _run_analysis_pipeline(raw_text, product, profile, db)
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
        answer = await gemini_product_chat(
            req.session_id, req.message, req.chat_history, analysis, evidence,
        )
        valid_ids = {e.citation_id for e in evidence}
        detected = {i.name_canonical for i in analysis.ingredients}
        answer = validate_chat_answer(answer, valid_ids, detected)
    except Exception as exc:
        logger.error("Gemini chat failed: %s", exc)
        raise HTTPException(502, f"Chat service error: {exc}")

    return ChatResponse(
        answer=answer.answer,
        citations_used=answer.citations_used,
    )
