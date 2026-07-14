# rename_partners

Portfolio-safe tooling for partner-name automation and operational spreadsheet synchronization.

## What it does
- renames partners through a partner platform API
- verifies the resulting name before marking the operation as successful
- retries transient failures without skipping the partner ID permanently
- keeps reporting spreadsheets synchronized after a rename is confirmed
- protects spreadsheet output from formula-like values

## Files
- src/main.py — rename workflow entry point
- src/sync_affiliate.py — follow-up sync for affiliate names
- src/portfolio_shared.py — shared API, OAuth, parsing, validation, and safety helpers
- .env.example — documented configuration template
- tests/ — regression tests for parsing, retries, validation, and CSV safety

## Installation
```bash
python -m pip install -e .[dev]
```

## Running
```bash
python -m src.main
python -m src.sync_affiliate
```

## Configuration
- Required values are documented in .env.example.
- AFFILKA_BASE_URL must use https and may be restricted via AFFILKA_ALLOWED_HOSTS.
- Google OAuth credentials should be stored locally and never committed.

## Testing
```bash
pytest -q tests/test_portfolio_automation.py
ruff check src tests
python -m compileall src
```