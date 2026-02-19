# LabelLens Backend

FastAPI backend powering LabelLens — ingredient analysis with Groq AI.

## Quick Start

```bash
cd backend

# Create virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# Run server
uvicorn app.main:app --reload --port 8000
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/scan/barcode` | Barcode lookup + full analysis |
| `POST` | `/api/scan/label` | Image upload (OCR) + analysis |
| `POST` | `/api/chat` | Product-locked chat |

## Example Requests

### Scan by barcode
```bash
curl -X POST http://127.0.0.1:8000/api/scan/barcode \
  -H "Content-Type: application/json" \
  -d '{
    "barcode": "5000159484695",
    "user_profile": {
      "vegan": true,
      "allergies": ["milk", "peanuts"],
      "avoid_terms": ["palm oil"]
    }
  }'
```

### Upload label image
```bash
curl -X POST http://127.0.0.1:8000/api/scan/label \
  -F "image=@label.jpg" \
  -F 'user_profile={"vegan": true, "allergies": ["soy"]}'
```

### Chat about scanned product
```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "<session_id from scan response>",
    "message": "Is this product safe for someone with a nut allergy?",
    "chat_history": []
  }'
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key |
| `DATABASE_URL` | No | SQLite URL (default: `sqlite:///./labellens.db`) |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins |
| `RATE_LIMIT_PER_MINUTE` | No | Requests per IP per minute (default: 30) |

## Running Tests

```bash
cd backend
python -m tests.test_rules_validators
```

## Architecture

- **Groq** structures ingredients and generates summaries/chat (never decides flags)
- **Rules engine** produces deterministic flags (allergens, diet, caffeine, umbrella terms, avoid terms)
- **Validators** ensure LLM output is schema-compliant, citation-valid, and medically safe
- **KB** (`kb/ingredients_kb.json`) provides evidence snippets with real citations
- **SQLite** stores sessions for chat continuity
