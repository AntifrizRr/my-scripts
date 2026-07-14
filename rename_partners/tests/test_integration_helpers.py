import pandas as pd
import pytest

from partner_automation.integration_helpers import (
    build_rename_mark,
    is_success_status,
    parse_allowed_hosts,
    parse_partner_ids,
    parse_rename_mark,
    safe_csv_value,
    should_process_partner_id,
    successful_partner_ids,
    validate_partner_base_url,
    validate_required_columns,
)
from partner_automation.sync_affiliate import build_confirmed_name_mapping


def test_parse_partner_ids_extracts_unique_numbers():
    assert parse_partner_ids("ids: 100, 200, 100") == [100, 200]


def test_parse_legacy_status_mark():
    mark = (
        "RENAMED 2024-01-01T00:00:00 | "
        "target='Example' | 100:renamed,200:error"
    )
    parsed = parse_rename_mark(mark)

    assert parsed["target_name"] == "Example"
    assert parsed["statuses"] == {100: "renamed", 200: "error"}


def test_build_and_parse_structured_status_mark():
    mark = build_rename_mark(
        "Example",
        {100: "renamed", 200: "verify_failed"},
    )
    parsed = parse_rename_mark(mark)

    assert parsed["target_name"] == "Example"
    assert parsed["statuses"] == {
        100: "renamed",
        200: "verify_failed",
    }


@pytest.mark.parametrize(
    "status",
    ["error", "cannot_fetch", "verify_failed", None],
)
def test_failed_or_missing_status_is_retried(status):
    assert should_process_partner_id(
        status=status,
        target_name="New name",
        previous_target_name="New name",
    )


@pytest.mark.parametrize("status", ["renamed", "noop"])
def test_successful_status_is_skipped_for_same_target(status):
    assert not should_process_partner_id(
        status=status,
        target_name="New name",
        previous_target_name="New name",
    )


def test_target_name_change_requeues_successful_id():
    assert should_process_partner_id(
        status="renamed",
        target_name="Another name",
        previous_target_name="Old name",
    )


def test_success_statuses_are_explicit():
    assert is_success_status("renamed")
    assert is_success_status("noop")
    assert not is_success_status("error")
    assert not is_success_status("verify_failed")


def test_structured_mark_returns_only_confirmed_ids():
    mark = "target='Example' | statuses=100:renamed,200:error,300:noop"

    assert successful_partner_ids(mark, [100, 200, 300]) == {
        100,
        300,
    }


def test_legacy_renamed_mark_keeps_backward_compatibility():
    assert successful_partner_ids(
        "RENAMED 2024-01-01",
        [100, 200],
    ) == {100, 200}


def test_confirmed_mapping_ignores_failed_partner_ids():
    dataframe = pd.DataFrame(
        [
            {
                "Partner ID": "100, 200",
                "Partner Name": "Example",
                "Rename": (
                    "target='Example' | "
                    "statuses=100:renamed,200:error"
                ),
            }
        ]
    )

    assert build_confirmed_name_mapping(dataframe) == {
        100: "Example"
    }


def test_validate_required_columns_reports_missing_columns():
    dataframe = pd.DataFrame([[1, 2]], columns=["A", "B"])

    with pytest.raises(ValueError) as error:
        validate_required_columns(
            dataframe,
            ["Partner ID", "Partner Name"],
            "Directory",
        )

    message = str(error.value)
    assert "Directory" in message
    assert "Partner ID" in message
    assert "A" in message


def test_parse_allowed_hosts():
    assert parse_allowed_hosts(
        "partner.example.com, api.example.com "
    ) == {"partner.example.com", "api.example.com"}


def test_validate_partner_base_url():
    assert (
        validate_partner_base_url(
            "https://partner.example.com",
            allowed_hosts={"partner.example.com"},
        )
        == "https://partner.example.com"
    )

    with pytest.raises(ValueError, match="HTTPS"):
        validate_partner_base_url("http://partner.example.com")

    with pytest.raises(ValueError, match="username or password"):
        validate_partner_base_url(
            "https://user:pass@partner.example.com"
        )

    with pytest.raises(ValueError, match="AFFILKA_ALLOWED_HOSTS"):
        validate_partner_base_url(
            "https://other.example.com",
            allowed_hosts={"partner.example.com"},
        )


@pytest.mark.parametrize("value", ["=cmd", "+1", "-calc", "@foo"])
def test_safe_csv_value_escapes_formula_like_values(value):
    assert safe_csv_value(value) == f"'{value}"


def test_safe_csv_value_keeps_plain_text():
    assert safe_csv_value("plain") == "plain"
