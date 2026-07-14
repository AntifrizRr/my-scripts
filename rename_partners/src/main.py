import csv
import glob
import os
import re
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import gspread
import pandas as pd
from dotenv import load_dotenv

from .integration_helpers import (
    GoogleOAuthClient,
    PartnerPlatformClient,
    build_rename_mark,
    norm_str,
    parse_allowed_hosts,
    parse_partner_ids,
    parse_rename_mark,
    safe_csv_value,
    should_process_partner_id,
    validate_partner_base_url,
    validate_required_columns,
)

COL_PARTNER_ID = "Partner ID"
COL_OLD_NAME = "OLD name"
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


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def make_run_log_path() -> str:
    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return os.path.join("logs", f"rename_partners_{timestamp}.csv")


def write_log(writer: csv.DictWriter, row: Dict[str, Any]) -> None:
    writer.writerow(row)
    print(
        f"[{row.get('ts_utc')}] row={row.get('sheet_row')} "
        f"partner_id={row.get('partner_id')} "
        f"action={row.get('action')} status={row.get('status')} "
        f"target='{row.get('target_name')}' note={row.get('note')}"
    )


def archive_old_logs(days: int) -> None:
    os.makedirs("logs", exist_ok=True)
    cutoff = datetime.now() - timedelta(days=days)
    candidates = []

    for path in glob.glob(os.path.join("logs", "rename_partners_*.csv")):
        try:
            if datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
                candidates.append(path)
        except OSError:
            continue

    if not candidates:
        return

    archive_path = os.path.join(
        "logs",
        f"archive_{datetime.now().strftime('%Y-%m')}.zip",
    )
    with zipfile.ZipFile(
        archive_path,
        "a",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archived_names = set(archive.namelist())
        for path in candidates:
            archive_name = os.path.basename(path)
            if archive_name not in archived_names:
                archive.write(path, arcname=archive_name)
            try:
                os.remove(path)
            except OSError:
                pass


def make_log_row(
    sheet_row: int,
    partner_id: Any,
    old_sheet_name: str,
    target_name: str,
    old_api_name: str,
    action: str,
    status: str,
    note: str,
) -> Dict[str, Any]:
    return {
        "ts_utc": utc_now().isoformat(),
        "sheet_row": sheet_row,
        "partner_id": partner_id,
        "old_sheet_name": old_sheet_name,
        "target_name": target_name,
        "old_api_name": old_api_name,
        "action": action,
        "status": status,
        "note": note,
    }


def load_api_settings() -> tuple[str, str, str, str, int]:
    base_url = (os.getenv("AFFILKA_BASE_URL", "") or "").strip()
    email = os.getenv("AFFILKA_OPERATOR_EMAIL", "")
    password = os.getenv("AFFILKA_OPERATOR_PASSWORD", "")
    totp_secret = os.getenv("AFFILKA_TOTP_SECRET", "")
    rpm = int(os.getenv("AFFILKA_RPM", "60"))

    if not base_url or not email or not password or not totp_secret:
        raise ValueError("Missing required AFFILKA_* values in .env.")

    allowed_hosts = parse_allowed_hosts(
        os.getenv("AFFILKA_ALLOWED_HOSTS", "")
    )
    validated_url = validate_partner_base_url(
        base_url,
        allowed_hosts=allowed_hosts,
    )
    return validated_url, email, password, totp_secret, rpm


def main() -> None:
    load_dotenv()

    sheet_id = (os.getenv("DIRECTORY_SHEET_ID", "") or "").strip()
    tab_name = (os.getenv("DIRECTORY_TAB_NAME", "") or "").strip()

    if not sheet_id or not tab_name:
        print(
            "Missing DIRECTORY_SHEET_ID or DIRECTORY_TAB_NAME in .env.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        base_url, email, password, totp_secret, rpm = load_api_settings()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    archive_old_logs(
        days=int(os.getenv("LOG_ARCHIVE_AFTER_DAYS", "30"))
    )
    log_path = make_run_log_path()
    fieldnames = [
        "ts_utc",
        "sheet_row",
        "partner_id",
        "old_sheet_name",
        "target_name",
        "old_api_name",
        "action",
        "status",
        "note",
    ]

    with open(log_path, "w", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(log_file, fieldnames=fieldnames)
        writer.writeheader()

        google_client = get_gspread_client()
        spreadsheet = google_client.open_by_key(sheet_id)
        worksheet = open_worksheet_fuzzy(spreadsheet, tab_name)
        dataframe = sheet_to_dataframe(worksheet)

        if dataframe.empty:
            print("Sheet is empty or contains no data rows.")
            return

        validate_required_columns(
            dataframe,
            [COL_PARTNER_ID, COL_NEW_NAME, COL_RENAME],
            tab_name,
        )

        client = PartnerPlatformClient(
            base_url,
            email,
            password,
            totp_secret,
            rpm=rpm,
        )
        print("== Partner platform login ==")
        client.login()

        rename_column_index = list(dataframe.columns).index(COL_RENAME)
        rename_column_letter = a1_column(rename_column_index)
        updates = []

        for index, row in dataframe.iterrows():
            sheet_row = index + 2
            raw_partner_ids = row.get(COL_PARTNER_ID, "")
            old_name = norm_str(row.get(COL_OLD_NAME, ""))
            target_name = norm_str(row.get(COL_NEW_NAME, ""))
            rename_mark = norm_str(row.get(COL_RENAME, ""))

            parsed_mark = parse_rename_mark(rename_mark)
            previous_target_name = parsed_mark.get("target_name", "")
            statuses = dict(parsed_mark.get("statuses", {}))

            if not target_name:
                write_log(
                    writer,
                    make_log_row(
                        sheet_row,
                        "",
                        old_name,
                        "",
                        "",
                        "SKIP",
                        "OK",
                        "Partner Name is empty.",
                    ),
                )
                continue

            partner_ids = parse_partner_ids(raw_partner_ids)
            if not partner_ids:
                write_log(
                    writer,
                    make_log_row(
                        sheet_row,
                        "",
                        old_name,
                        target_name,
                        "",
                        "SKIP",
                        "OK",
                        "Partner ID is empty or invalid.",
                    ),
                )
                continue

            pending_ids = [
                partner_id
                for partner_id in partner_ids
                if should_process_partner_id(
                    statuses.get(partner_id),
                    target_name,
                    previous_target_name,
                )
            ]

            if not pending_ids:
                continue

            for partner_id in pending_ids:
                current_name = client.get_partner_name(partner_id)

                if current_name is None:
                    statuses[partner_id] = "cannot_fetch"
                    write_log(
                        writer,
                        make_log_row(
                            sheet_row,
                            partner_id,
                            old_name,
                            target_name,
                            "",
                            "CHECK",
                            "ERR",
                            "Could not read the current name from the API.",
                        ),
                    )
                    continue

                if norm_str(current_name) == target_name:
                    statuses[partner_id] = "noop"
                    write_log(
                        writer,
                        make_log_row(
                            sheet_row,
                            partner_id,
                            old_name,
                            target_name,
                            current_name,
                            "NOOP",
                            "OK",
                            "The API already contains the target name.",
                        ),
                    )
                    continue

                try:
                    client.rename_partner(partner_id, target_name)
                    verified_name = client.get_partner_name(partner_id) or ""

                    if norm_str(verified_name) == target_name:
                        statuses[partner_id] = "renamed"
                        result_status = "OK"
                        note = "Name updated and verified."
                    else:
                        statuses[partner_id] = "verify_failed"
                        result_status = "WARN"
                        note = (
                            "Update request completed, but verification "
                            f"returned '{verified_name}'."
                        )

                    write_log(
                        writer,
                        make_log_row(
                            sheet_row,
                            partner_id,
                            old_name,
                            target_name,
                            current_name,
                            "RENAME",
                            result_status,
                            note,
                        ),
                    )
                except Exception as exc:
                    statuses[partner_id] = "error"
                    write_log(
                        writer,
                        make_log_row(
                            sheet_row,
                            partner_id,
                            old_name,
                            target_name,
                            current_name,
                            "RENAME",
                            "ERR",
                            str(exc)[:800],
                        ),
                    )

            mark = safe_csv_value(build_rename_mark(target_name, statuses))
            updates.append(
                {
                    "range": f"{rename_column_letter}{sheet_row}",
                    "values": [[mark]],
                }
            )

        if updates:
            worksheet.batch_update(updates, value_input_option="RAW")
            print(f"Updated Rename marks: {len(updates)} row(s).")
        else:
            print("Nothing to update.")

        print(f"Log: {log_path}")


if __name__ == "__main__":
    main()
