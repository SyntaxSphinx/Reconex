# Reconex

**Reconex** is an AI-assisted Finance Controller for merchant settlement reconciliation (fintech hackathon simulation).

It reconciles three synthetic ledgers:

1. Merchant payment records  
2. Razorpay-inspired settlement reconciliation records  
3. Merchant bank transactions  

A **deterministic** engine is the financial source of truth. An optional LLM may investigate eligible exceptions using bounded evidence only. Ground truth exists for evaluation and is never used during reconciliation or AI investigation.

## What's Implemented

- Synthetic data generation with reproducible seeds and controlled anomaly injection
- Deterministic reconciliation engine (integer-paise arithmetic; payment- and batch-level results)
- Reconciliation **runs** with scenario selection and persisted run history
- Deterministic failure **scenarios** (e.g. Normal Day, Refund Spike, Settlement Delay, Duplicate Payment, Bank File Issue)
- FastAPI backend exposing runs, payments, investigations, analytics, and health
- React operations console: Overview, Payments, Investigations, Analytics, and Investigation Detail (deterministic evidence and recommendation)
- Optional AI-assisted exception investigation via an OpenAI-compatible API (`POST /api/investigations/{id}/run-ai`)
- Independent evaluation harness against `ground_truth.json`
- Backend test suite: **165** tests passing; frontend **lint** and **production build** passing

## What's Not Implemented

- Database persistence (run history is workspace/file-backed for the demo)
- Authentication
- Live Razorpay API integration
- Autonomous agents or automatic financial resolution (AI cannot modify records or mark exceptions resolved)
- Production deployment

## Architecture

```
Synthetic CSVs  →  Workspace (+ optional scenario)  →  ReconciliationEngine
                                                              ↓
                                                    Current run + history
                                                              ↓
                              FastAPI (/api/runs, /payments, /investigations, /analytics)
                                                              ↓
                                              React operations console (Vite)
```

**Deterministic vs AI**

| Layer | Role |
| --- | --- |
| Deterministic reconciliation | Authoritative. Classifies matches, pending states, and exceptions. Powers Payments, Investigations, Analytics, and Investigation Detail evidence. |
| AI investigation | Optional and secondary. Runs only after an exception exists, on bounded evidence from the deterministic layer. Never changes ledger data. |

Reconciliation, the console, and Investigation Detail work **without** an LLM or API key. AI assist requires `RECONEX_LLM_API_KEY` and a provider account with available quota/credits.

## Setup

### Backend

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Generate synthetic data (if needed)
python -m scripts.generate_data --records 1000 --seed 42

# Start API (http://127.0.0.1:8000)
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Health check: http://127.0.0.1:8000/health

### Frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173 (proxies /api to the backend)
```

Build / lint:

```bash
cd frontend
npm run lint
npm run build
```

### Optional AI investigation

Supply an OpenAI-compatible API key through the **environment only**. Never commit keys or `.env` files.

```bash
# Windows PowerShell (current session)
$env:RECONEX_LLM_API_KEY = "your-key-here"

# Then start the backend in that same session
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

| Variable | Purpose | Default |
| --- | --- | --- |
| `RECONEX_LLM_API_KEY` | Provider API key | unset (AI disabled) |
| `RECONEX_LLM_MODEL` | Model name | `gpt-4o-mini` |
| `RECONEX_LLM_BASE_URL` | OpenAI-compatible base URL | `https://api.openai.com/v1` |
| `RECONEX_LLM_TIMEOUT_SECONDS` | Request timeout | `30` |
| `RECONEX_AI_CONFIDENCE_THRESHOLD` | Escalate below this confidence | `0.75` |

### Tests and evaluation

```bash
pytest tests/ -v
python -m scripts.evaluate --data-dir data/generated
```

## Project Structure

```
backend/app/
  models/            # Pydantic domain models
  generator/         # Synthetic data generation
  reconciliation/    # Deterministic reconciliation engine
  evaluation/        # Independent evaluation harness
  investigation/     # Optional AI investigator (exceptions only)
  workspace/         # Run store, scenarios, API projections
  api/               # FastAPI routers and schemas
  main.py            # Application entry
frontend/            # React + TypeScript + Vite operations console
scripts/             # Data generation and evaluation CLIs
tests/               # pytest suite
data/generated/      # Synthetic datasets (gitignored)
data/runs/           # Persisted run history (gitignored)
docs/                # Data model, reconciliation rules, AI investigation spec
```

## Anomaly Families

1. **MISSING_SETTLEMENT** — Payment captured but settlement record missing  
2. **MISSING_BANK_CREDIT** — Settlement complete but bank credit missing  
3. **AMOUNT_MISMATCH** — Bank amount differs from expected  
4. **DUPLICATE** — Duplicate settlement records  
5. **REFUND_MISMATCH** — Refund handling inconsistency  
6. **UNMATCHED_REFERENCE** — Corrupted UTR or matching identifier  

See `docs/data-model.md` and `docs/reconciliation-rules.md`.

## AI Usage Disclosure

AI is used only to investigate exceptions the deterministic engine has already classified.

**Used for:** evidence synthesis, hypothesis/explanation, confidence, and recommended next action.  

**Not used for:** authoritative calculations, matching, mutating IDs/amounts/UTRs/timestamps, or auto-resolving records.

The AI layer never receives `ground_truth.json`. Findings must cite supplied evidence IDs; uncited, malformed, or low-confidence responses escalate to human review. Provider failures leave the deterministic result unchanged.

## Technology Stack

- Python 3.11+, Pydantic v2, FastAPI, uvicorn, pytest  
- React 19, TypeScript, Vite  

## Notes

- Amounts are integer **paise** (1 INR = 100 paise); fee/tax/variance use integer arithmetic only  
- Data generation is deterministic for a given seed  
- Generated and run artifacts under `data/` are gitignored  
- Hackathon simulation — not a production system  

## License

Hackathon project. License TBD.
