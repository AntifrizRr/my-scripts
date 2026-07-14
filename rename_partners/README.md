# Partner Rename Scripts

This directory contains two related Python scripts.

## `main.py`

Reads partner IDs and target names from Google Sheets, updates names through the partner platform API, and verifies the result.

The script stores a status for each partner ID so that:

- successful operations are skipped on the next run;
- failed operations can be retried;
- changing the target name starts a new processing attempt.

## `sync_affiliate.py`

Reads successfully processed partner IDs and synchronizes the confirmed names with another Google Sheet.

Before updating a row, the script checks the current name through the API.

## Configuration

Copy `.env.example` and provide local values for:

- API URL and credentials;
- Google OAuth files;
- spreadsheet IDs and tab names.

Credentials and production identifiers must not be committed.

## Running

```bash
python -m partner_automation.main
python -m partner_automation.sync_affiliate
```

## Checks

```bash
python -m pytest -q
python -m ruff check partner_automation tests
python -m compileall partner_automation
```

The tests cover helper functions and status-processing rules. External API and Google Sheets integrations require local access and are not tested end to end.
