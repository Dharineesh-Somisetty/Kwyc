# LabelLens

AI-powered food & drink ingredient scanner with personalized conflict detection and product-locked chat.

## Architecture

| Layer | Tech | Location |
|-------|------|----------|
| Frontend | React 19 + Vite + Tailwind CSS | `webapp/` |
| Backend | FastAPI + Gemini + SQLite | `backend/` |
| Knowledge Base | JSON (40 ingredient entries) | `backend/kb/` |

## Running Locally (2 terminals)

### Terminal 1 — Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # ← add your GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```

### Terminal 2 — Frontend

```bash
cd webapp
npm install
cp .env.example .env        # uses http://127.0.0.1:8000 by default
npm run dev
```

Open **http://localhost:5173** in your browser.

## Features

- **Barcode scan** → Open Food Facts lookup
- **Label photo upload** → OCR (pytesseract) fallback
- **Groq-powered** ingredient structuring & personalized summaries
- **Deterministic rules engine** for allergens, diet conflicts, caffeine, umbrella terms, and avoid-terms
- **Product-locked chatbot** — only answers about the currently scanned product
- **Evidence citations** from a curated knowledge base with clickable source links
- **Security**: API keys only on backend via env vars, rate limiting, request validation

## Example curl

```bash
curl -X POST http://127.0.0.1:8000/api/scan/barcode \
  -H "Content-Type: application/json" \
  -d '{"barcode":"5000159484695","user_profile":{"vegan":true,"allergies":["milk"]}}'
```

## Tests

```bash
cd backend && python -m tests.test_rules_validators
```
