import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.portfolio_shared import (
    build_rename_mark,
    parse_partner_ids,
    parse_rename_mark,
    safe_csv_value,
    validate_affilka_base_url,
    validate_required_columns,
)


def test_parse_partner_ids_extracts_unique_numbers():
    assert parse_partner_ids("ids: 100, 200, 100") == [100, 200]


def test_parse_legacy_status_mark():
    mark = "RENAMED 2024-01-01T00:00:00 | target='Example' | 100:renamed,200:error"
    parsed = parse_rename_mark(mark)
    assert parsed["target_name"] == "Example"
    assert parsed["statuses"][100] == "renamed"
    assert parsed["statuses"][200] == "error"


def test_parse_structured_status_mark():
    mark = "target='Example' | statuses=100:renamed,200:verify_failed"
    parsed = parse_rename_mark(mark)
    assert parsed["target_name"] == "Example"
    assert parsed["statuses"][200] == "verify_failed"


def test_build_rename_mark_uses_structured_format():
    mark = build_rename_mark("Example", {100: "renamed", 200: "error"})
    assert "target='Example'" in mark
    assert "100:renamed" in mark
    assert "200:error" in mark


def test_retries_error_statuses_for_new_run():
    mark = build_rename_mark("Example", {100: "error"})
    parsed = parse_rename_mark(mark)
    assert parsed["statuses"][100] == "error"


def test_retries_verify_failed_statuses_for_new_run():
    mark = build_rename_mark("Example", {100: "verify_failed"})
    parsed = parse_rename_mark(mark)
    assert parsed["statuses"][100] == "verify_failed"


def test_skips_successful_statuses_for_same_target_name():
    parsed = parse_rename_mark("target='Example' | statuses=100:noop")
    assert parsed["statuses"][100] == "noop"


def test_target_name_change_requeues_partner_id():
    parsed = parse_rename_mark("target='Old' | statuses=100:renamed")
    assert parsed["target_name"] == "Old"


def test_multiple_ids_with_different_statuses_are_preserved():
    parsed = parse_rename_mark("target='Example' | statuses=100:renamed,200:error")
    assert parsed["statuses"][100] == "renamed"
    assert parsed["statuses"][200] == "error"


def test_validate_required_columns_raises_with_sheet_name_and_found_columns():
    df = pd.DataFrame([[1, 2]], columns=["A", "B"])
    try:
        validate_required_columns(df, ["Partner ID", "Partner Name"], "Directory")
    except ValueError as exc:
        message = str(exc)
        assert "Directory" in message
        assert "Partner ID" in message
        assert "A" in message


def test_validate_affilka_base_url_requires_https_and_allowed_host():
    validate_affilka_base_url("https://partner.example.com", allowed_hosts={"partner.example.com"})
    try:
        validate_affilka_base_url("http://partner.example.com")
    except ValueError as exc:
        assert "https" in str(exc).lower()


def test_validate_affilka_base_url_rejects_credentials_and_disallowed_host():
    try:
        validate_affilka_base_url("https://user:pass@partner.example.com")
    except ValueError as exc:
        assert "username" in str(exc).lower() or "password" in str(exc).lower()

    try:
        validate_affilka_base_url("https://evil.example.com", allowed_hosts={"partner.example.com"})
    except ValueError as exc:
        assert "allowed" in str(exc).lower()


def test_safe_csv_value_escapes_formula_like_values():
    assert safe_csv_value("=cmd") == "'=cmd"
    assert safe_csv_value("+1") == "'+1"
    assert safe_csv_value("-calc") == "'-calc"
    assert safe_csv_value("@foo") == "'@foo"
    assert safe_csv_value("plain") == "plain"
