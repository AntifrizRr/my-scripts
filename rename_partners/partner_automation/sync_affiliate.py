import os
import re
import sys
from typing import Dict, Iterable, List, Tuple

import gspread
import pandas as pd
from dotenv import load_dotenv

from .integration_helpers import (
    GoogleOAuthClient,
    PartnerPlatformClient,
    norm_str,
    parse_allowed_hosts,
    parse_partner_ids,
    safe_csv_value,
    successful_partner_ids,
    validate_partner_base_url,
    validate_required_columns,
)

COL_PARTNER_ID = "Partner ID"
COL_NEW_NAME = "Partner Name"
COL_RENAME = "Rename"


def normalize_worksheet_title(value: str) -> str:
    value = (value or "").replace("\u00a0", " ").strip()
    value = re.sub(r"\s+", " ", value)
    return value.casefold()


def open_worksheet_fuzzy(
    spreadsheet: gspread.Spreadsheet,
    title: str,
) -> gspread.Worksheet:
    try:
        return spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        pass

    normalized_title = normalize_worksheet_title(title)
    worksheets = spreadsheet.worksheets()

    for worksheet in worksheets:
        if normalize_worksheet_title(worksheet.title) == normalized_title:
            print(f"[sheet] requested='{title}' matched='{worksheet.title}'")
            return worksheet

    available = [worksheet.title for worksheet in worksheets]
    raise gspread.exceptions.WorksheetNotFound(
        f"{title!r}. Available tabs: {available}"
    )


def get_gspread_client():
    client = GoogleOAuthClient(
        auth_mode=os.getenv("GOOGLE_AUTH_MODE", "oauth"),
        creds_path=os.getenv("GOOGLE_OAUTH_CLIENT_FILE", "credentials.json"),
        token_path=os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "token.json"),
    )
    return client.get_client()


def sheet_to_dataframe(worksheet) -> pd.DataFrame:
    values = worksheet.get_all_values()
    if not values or len(values) < 2:
        return pd.DataFrame()
    return pd.DataFrame(values[1:], columns=values[0])


def a1_column(column_index_zero_based: int) -> str:
    number = column_index_zero_based + 1
    result = ""
    while number > 0:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def chunks(
    values: List[Tuple[str, List[str]]],
    size: int,
) -> Iterable[List[Tuple[str, List[str]]]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def load_api_settings() -> tuple[str, str, str, str, int]:
    base_url = (os.getenv("AFFILKA_BASE_URL", "") or "").strip()
    email = os.getenv("AFFILKA_OPERATOR_EMAIL", "")
    operator_password = os.getenv("AFFILKA_OPERATOR_PASSWORD", "")
    totp_secret = os.getenv("AFFILKA_TOTP_SECRET", "")
    rpm = int(os.getenv("AFFILKA_RPM", "60"))

    if not base_url or not email or not operator_password or not totp_secret:
        raise ValueError("Missing required AFFILKA_* values in .env.")

    allowed_hosts = parse_allowed_hosts(
        os.getenv("AFFILKA_ALLOWED_HOSTS", "")
    )
    validated_url = validate_partner_base_url(
        base_url,
        allowed_hosts=allowed_hosts,
    )
    return validated_url, email, operator_password, totp_secret, rpm


def build_confirmed_name_mapping(
    dataframe: pd.DataFrame,
) -> Dict[int, str]:
    """Build a mapping only from confirmed rename results."""

    mapping: Dict[int, str] = {}

    for _, row in dataframe.iterrows():
        target_name = norm_str(row.get(COL_NEW_NAME, ""))
        if not target_name:
            continue

        partner_ids = parse_partner_ids(row.get(COL_PARTNER_ID, ""))
        confirmed_ids = successful_partner_ids(
            row.get(COL_RENAME, ""),
            partner_ids,
        )

        for partner_id in confirmed_ids:
            mapping[partner_id] = target_name

    return mapping


def main() -> None:
    load_dotenv()

    plan_sheet_id = (os.getenv("PLAN_FACT_SHEET_ID", "") or "").strip()
    plan_tab = (os.getenv("PLAN_FACT_TAB_NAME", "") or "").strip()
    directory_sheet_id = (
        os.getenv("DIRECTORY_SHEET_ID", "") or ""
    ).strip()
    directory_tab = (os.getenv("DIRECTORY_TAB_NAME", "") or "").strip()
    affiliate_id_column = (
        os.getenv("PLAN_FACT_COL_AFF_ID", "Affiliate ID") or ""
    ).strip()
    affiliate_name_column = (
        os.getenv("PLAN_FACT_COL_AFF_NAME", "Affiliate") or ""
    ).strip()

    if (
        not plan_sheet_id
        or not plan_tab
        or not directory_sheet_id
        or not directory_tab
    ):
        print(
            "Missing PLAN_FACT_* or DIRECTORY_* values in .env.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        base_url, email, operator_password, totp_secret, rpm = load_api_settings()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    google_client = get_gspread_client()

    directory_spreadsheet = google_client.open_by_key(directory_sheet_id)
    directory_worksheet = open_worksheet_fuzzy(
        directory_spreadsheet,
        directory_tab,
    )
    directory_dataframe = sheet_to_dataframe(directory_worksheet)

    if directory_dataframe.empty:
        print("Directory sheet is empty.")
        return

    validate_required_columns(
        directory_dataframe,
        [COL_PARTNER_ID, COL_NEW_NAME, COL_RENAME],
        directory_tab,
    )

    mapping = build_confirmed_name_mapping(directory_dataframe)
    if not mapping:
        print("Nothing to sync: no confirmed rename results.")
        return

    client = PartnerPlatformClient(
        base_url,
        email,
        operator_password,
        totp_secret,
        rpm=rpm,
    )
    print("== Partner platform login ==")
    client.login()

    plan_spreadsheet = google_client.open_by_key(plan_sheet_id)
    plan_worksheet = open_worksheet_fuzzy(plan_spreadsheet, plan_tab)
    plan_dataframe = sheet_to_dataframe(plan_worksheet)

    if plan_dataframe.empty:
        print("Target sheet is empty.")
        return

    validate_required_columns(
        plan_dataframe,
        [affiliate_id_column, affiliate_name_column],
        plan_tab,
    )

    affiliate_name_index = list(plan_dataframe.columns).index(
        affiliate_name_column
    )
    affiliate_name_letter = a1_column(affiliate_name_index)

    updates: List[Tuple[str, List[str]]] = []
    checked = 0
    already_correct = 0
    api_mismatch = 0
    cannot_fetch = 0
    no_mapping = 0

    for index, row in plan_dataframe.iterrows():
        sheet_row = index + 2
        partner_ids = parse_partner_ids(row.get(affiliate_id_column, ""))

        if not partner_ids:
            continue

        partner_id = partner_ids[0]
        target_name = mapping.get(partner_id)

        if not target_name:
            no_mapping += 1
            continue

        current_api_name = client.get_partner_name(partner_id)
        checked += 1

        if current_api_name is None:
            cannot_fetch += 1
            print(
                f"[skip] row={sheet_row} partner_id={partner_id}: "
                "could not read the API value"
            )
            continue

        if norm_str(current_api_name) != target_name:
            api_mismatch += 1
            print(
                f"[skip] row={sheet_row} partner_id={partner_id}: "
                f"API value '{current_api_name}' does not match "
                f"confirmed value '{target_name}'"
            )
            continue

        current_sheet_name = norm_str(row.get(affiliate_name_column, ""))
        if current_sheet_name == target_name:
            already_correct += 1
            continue

        updates.append(
            (
                f"{affiliate_name_letter}{sheet_row}",
                [safe_csv_value(target_name)],
            )
        )

    for batch in chunks(updates, 500):
        plan_worksheet.batch_update(
            [
                {"range": cell_range, "values": [values]}
                for cell_range, values in batch
            ],
            value_input_option="RAW",
        )

    print("Sync completed.")
    print(f"- confirmed mapping: {len(mapping)}")
    print(f"- checked through API: {checked}")
    print(f"- updated cells: {len(updates)}")
    print(f"- already correct: {already_correct}")
    print(f"- API mismatch: {api_mismatch}")
    print(f"- could not fetch: {cannot_fetch}")
    print(f"- no confirmed mapping: {no_mapping}")


if __name__ == "__main__":
    main()
