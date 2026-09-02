# Reconex

**Reconex** is an AI-assisted Finance Controller for merchant settlement reconciliation, designed for a fintech hackathon.

The system reconciles:
1. Merchant payment records
2. Razorpay-inspired settlement reconciliation records
3. Merchant bank transactions

A deterministic engine classifies matches, pending states, and exceptions. An independent harness evaluates that engine against synthetic `ground_truth.json`. An LLM investigates eligible unresolved exceptions and returns a structured recommendation. Ground truth is for evaluation only; it is never used during reconciliation or AI investigation.

## Current Phase: Phase 3B — AI Exception Investigation

Phases 1–3B are implemented: synthetic data generation, deterministic reconciliation, independent evaluation, and bounded AI investigation of reconciliation exceptions.

### What's Implemented

- Typed domain models (Pydantic v2) for payments, settlement records, and bank transactions
- Synthetic data generator with reproducible seeds and controlled anomaly injection
- Ground-truth generation for **evaluation only**
- Deterministic reconciliation engine (integer-paise arithmetic; payment-level and batch-level results)
- Independent evaluation harness against `ground_truth.json`
- AI investigator for eligible exceptions: bounded evidence, structured finding, confidence, and recommended next action
- Minimal FastAPI health-check endpoint
- Automated test suite (**124 tests** currently passing)

### What's NOT Implemented

- Frontend
- Database persistence
- Authentication
- Live Razorpay API integration
- Autonomous agents
- Automatic AI financial resolution (AI cannot modify records or mark exceptions resolved)
- Production deployment

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Generate Synthetic Data

Generate 1,000 records with seed 42 (default):

```bash
python -m scripts.generate_data --records 1000 --seed 42
```

Generate a smaller dataset:

```bash
python -m scripts.generate_data --records 100 --seed 123
```

Generate clean data without anomalies:

```bash
python -m scripts.generate_data --records 1000 --seed 42 --no-anomalies
```

Custom output directory:

```bash
python -m scripts.generate_data --records 1000 --seed 42 --output-dir data/my_dataset
```

### Evaluate Reconciliation

Evaluate the deterministic engine against `ground_truth.json` (evaluation only; the engine does not read ground truth):

```bash
python -m scripts.evaluate --data-dir data/generated
```

### Generated Files

The generator produces the following files in `data/generated/`:

- **`payments.csv`** - Merchant payment records
- **`settlement_recon.csv`** - Settlement reconciliation records
- **`bank_transactions.csv`** - Bank transaction records
- **`ground_truth.json`** - Ground truth describing injected anomalies (for evaluation only)

**Important**: All generated data is synthetic. Do not use real customer information.

### Run Health Check

Start the FastAPI application:

```bash
uvicorn backend.app.main:app --reload
```

Visit http://localhost:8000/health to verify the service is running.

### Run Tests

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ --cov=backend --cov-report=html
```

## Project Structure

```
backend/
  app/
    models/           # Pydantic domain models
    generator/        # Synthetic data generation
    reconciliation/   # Deterministic reconciliation engine
    evaluation/       # Independent evaluation harness
    investigation/    # AI investigator (exceptions only)
    main.py           # FastAPI application
scripts/
  generate_data.py    # Data generation script
tests/                # pytest test suite
data/
  generated/          # Generated datasets (gitignored)
docs/
  data-model.md               # Data model documentation
  reconciliation-rules.md     # Deterministic reconciliation rules
  ai-investigation-spec.md    # AI investigation boundaries
```

## Anomaly Types

Phase 1 implements 6 anomaly families:

1. **MISSING_SETTLEMENT** - Payment captured but settlement record missing
2. **MISSING_BANK_CREDIT** - Settlement complete but bank credit missing
3. **AMOUNT_MISMATCH** - Bank transaction amount differs from expected
4. **DUPLICATE** - Duplicate settlement records
5. **REFUND_MISMATCH** - Inconsistency in refund handling
6. **UNMATCHED_REFERENCE** - Corrupted UTR or matching identifier

See `docs/data-model.md` for detailed specifications.

## AI Usage Disclosure

Reconex uses AI **only** to investigate reconciliation exceptions that the deterministic
engine has already classified. The deterministic engine remains the financial source of truth.

AI is used for:
- exception investigation and evidence synthesis
- root-cause hypothesis and explanation
- investigation confidence assessment
- recommending the next operational action

AI is **not** used for:
- authoritative financial calculations
- deterministic reconciliation or transaction matching
- modifying payments, settlements, bank records, IDs, UTRs, amounts or timestamps
- creating, deleting or auto-resolving financial records

The AI layer receives only bounded evidence produced by the deterministic engine, never
`ground_truth.json`. Every finding must cite supplied evidence IDs; uncited, malformed or
low-confidence responses are escalated to human review, and any AI failure leaves the
deterministic reconciliation result unchanged.

LLM configuration is read from environment variables (no keys in the repository):

| Variable | Purpose | Default |
| --- | --- | --- |
| `RECONEX_LLM_API_KEY` | Provider API key | unset (AI disabled) |
| `RECONEX_LLM_MODEL` | Model name | `gpt-4o-mini` |
| `RECONEX_LLM_BASE_URL` | OpenAI-compatible base URL | `https://api.openai.com/v1` |
| `RECONEX_LLM_TIMEOUT_SECONDS` | Request timeout | `30` |
| `RECONEX_AI_CONFIDENCE_THRESHOLD` | Escalate below this confidence | `0.75` |

## Technology Stack

- Python 3.11+
- Pydantic v2 (data validation)
- FastAPI (API framework)
- pytest (testing)

## Important Notes

- All monetary amounts are stored as **integer paise** (1 INR = 100 paise)
- Fee/tax/variance use integer arithmetic only (`amount * 18 // 1000`, `fee * 18 // 100`)
- Anomaly counts are rate-based (default 3.5% of records on a 1,000-record dataset)
- Data generation is **deterministic** — same seed produces byte-for-byte identical output
- Ground truth is for **evaluation only** - the application does not use it during reconciliation
- This is a **hackathon simulation**, not a production system

## License

This is a hackathon project. License TBD.
