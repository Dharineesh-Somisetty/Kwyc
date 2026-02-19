# BuyRight — Smart Food Ingredient Scanner

One-liner

- Quickly understand how healthy and suitable a packaged food product is for you, using a clear ingredient score, explanations, and alternatives.

Problem

- Ingredient lists are long, confusing, and hide important information (allergens, unexpected additives, processing aids).
- Shoppers with dietary needs (allergies, intolerances, vegan, kosher, low-sugar, etc.) lack simple, trustworthy signals in-store.

The solution I'm proposing:

- BuyRight scans or accepts an ingredient list and returns:
  - A single, interpretable `BuyRight Score` reflecting healthiness and suitability for the user.
  - Highlighted problem ingredients with short, human-readable explanations and severity levels.
  - Recommended alternative ingredients/products and swaps.
  - Personalization by diet, allergies, and priorities (organic, non-GMO, low sugar, etc.).

What the repo already contains (starter assets)

- A Python backend with a rules engine, scorer, validators, and services.
- Knowledge base: `ingredients master` data.
- A React/Vite webapp for UI.
- Test cases showing current scorer and rules behavior.

Key differentiators

- Rule-based explainability + ML/scoring hybrid for transparent results.
- Multi-platform: web + mobile scanning for in-store use.
- Extensible knowledge base for new diets and regional ingredient variants.

Target users

- Health-conscious shoppers, people with allergies or specific diets, caregivers, and retailers wanting to offer product transparency.

Core features (MVP)

1. Ingredient parsing from text or image OCR.
2. Rule-based detection for allergens, additives, and flagged ingredients.
3. `BuyRight Score` with a concise explanation and severity badges.
4. Personalized settings (allergies, dietary preferences, priorities).
5. Simple web UI and mobile scanning flow.

Architecture & tech stack

- Backend: Python (existing codebase) — FastAPI-compatible patterns, rules engine, scorer modules, unit tests.
- Data: pandas-based data pipeline, knowledge base JSON/CSV.
- Frontend: React + Vite (webapp).
- LLM augmentation for better explanations (there are service placeholders in `backend/app/services`).
- Deployment: I plan to do it with Docker images, host frontends on Vercel/Netlify and backend on a small cloud VM or managed service.

Data & privacy

- Uses curated ingredient knowledgebase and public datasets; all processing can happen client-side or on your server depending on deployment.
- No need to store personal health data; user preferences may be stored locally or encrypted if persisted.

Milestones (4–8 weeks roadmap)

- Week 1: MVP scorer + rules validation; CLI/web endpoint for ingredient input.
- Week 2: OCR integration + mobile scanning proof-of-concept.
- Week 3: Web UI scaffolding + personalization settings.
- Week 4: Improve scoring, add alternative suggestions and UX polish.
- Weeks 5–8: Testing with sample products, onboarding content, deploy alpha, gather feedback.

Success metrics

- Accuracy of allergen/ingredient detection (test coverage & golden samples).
- User clarity: average time to understand product results, Net Promoter Score (NPS) in early testers.
- Engagement: number of scans per user and retention after 1 week.

What I'm looking to do further:

- Frontend developer to build the web UI and dashboards.
- Polish camera/scan flow and OCR integration.
- Backend/Python engineering to harden the rules engine, scoring logic, and API endpoints.
- Data engineering / ML engineering to expand the Knowledge Base, create evaluation datasets, and tune scoring.
- UX/Product desiging to craft clear explanations, badges, and user flows.


