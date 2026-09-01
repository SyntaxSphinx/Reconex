# Reconex

**Reconex** is an AI-assisted Finance Controller for merchant settlement reconciliation, designed for a fintech hackathon.

The eventual system will reconcile:
1. Merchant payment records
2. Razorpay-inspired settlement reconciliation records  
3. Merchant bank transactions

against known ground truth, detect exceptions, and use an LLM to investigate unresolved exceptions.

## Current Phase: Phase 1 - Data Generation

**Phase 1 Goal**: Build the foundation for synthetic data generation with controlled anomaly injection.

### What's Implemented

- ✅ Clean Python backend project structure
- ✅ Typed domain models (Pydantic v2) for Payments, Settlement Records, Bank Transactions
- ✅ Synthetic data generator with reproducible seeds
- ✅ Controlled anomaly injection (6 anomaly types)
- ✅ Ground-truth generation for evaluation
- ✅ Automated test suite (pytest)
- ✅ Minimal FastAPI health-check endpoint
- ✅ Project documentation

### What's NOT Implemented (Yet)

- ❌ Reconciliation engine
- ❌ Exception detection and classification
- ❌ AI/LLM investigation
- ❌ Frontend
- ❌ Database persistence
- ❌ Authentication
- ❌ Razorpay live API integration

These features will be added in future phases.

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
    main.py           # FastAPI application
scripts/
  generate_data.py    # Data generation script
tests/                # pytest test suite
data/
  generated/          # Generated datasets (gitignored)
docs/
  data-model.md       # Data model documentation
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
