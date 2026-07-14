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

from .portfolio_shared import (
    ClientClient,
    GoogleOAuthClient,
    build_rename_mark,
    norm_str,
    parse_partner_ids,
    parse_rename_mark,
    safe_csv_value,
    should_process_partner_id,
    validate_required_columns,
)

# ============================================================
# Columns in DIRECTORY_TAB
# ============================================================
COL_PARTNER_ID = "Partner ID"
COL_OLD_NAME = "OLD name"
COL_NEW_NAME = "Partner Name"
COL_RENAME = "Rename"

# ============================================================
# Google OAuth
# ============================================================

def _norm_ws_title(s: str) -> str:
    # normalize: trim, collapse whitespace (incl. NBSP), casefold
    s = (s or "").replace("\u00a0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s.casefold()


def open_worksheet_fuzzy(sh: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    """
    Tries to open worksheet by exact title; if not found, tries fuzzy match:
    - trims
    - collapses whitespace
    - case-insensitive
    Prints available sheet titles on failure.
    """
    wanted_raw = title or ""
    wanted = _norm_ws_title(wanted_raw)
    try:
        return sh.worksheet(wanted_raw)
    except Exception:
        pass

    # Fuzzy match
    wss = sh.worksheets()
    for ws in wss:
        if _norm_ws_title(ws.title) == wanted:
            print(
                f"[ws] Fuzzy matched worksheet: requested='{wanted_raw}' -> actual='{ws.title}'"
            )
            return ws

    titles = [ws.title for ws in wss]
    raise gspread.exceptions.WorksheetNotFound(
        f"{wanted_raw!r}. Available tabs: {titles}"
    )


def get_gspread_client():
    client = GoogleOAuthClient(
        auth_mode=os.getenv("GOOGLE_AUTH_MODE", "oauth"),
        creds_path=os.getenv("GOOGLE_OAUTH_CLIENT_FILE", "credentials.json"),
        token_path=os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "token.json"),
    )
    return client.get_client()


def sheet_to_df(ws) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return pd.DataFrame()
    header = values[0]
    rows = values[1:]
    return pd.DataFrame(rows, columns=header)


def ensure_columns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df


def ensure_required_columns(df: pd.DataFrame, cols: List[str], sheet_name: str) -> None:
    validate_required_columns(df, cols, sheet_name)


def a1_col(col_idx_0_based: int) -> str:
    n = col_idx_0_based + 1
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


# ============================================================
# Logging
# ============================================================
def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def make_run_log_path() -> str:
    os.makedirs("logs", exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return os.path.join("logs", f"rename_partners_{ts}.csv")


def log_print(writer: csv.DictWriter, row: Dict[str, Any]) -> None:
    writer.writerow(row)
    print(
        f"[{row.get('ts_utc')}] row={row.get('sheet_row')} partner_id={row.get('partner_id')} "
        f"action={row.get('action')} status={row.get('status')} "
        f"api_old='{row.get('old_api_name')}' target='{row.get('target_name')}' note={row.get('note')}"
    )


def archive_old_logs(days: int) -> None:
    os.makedirs("logs", exist_ok=True)
    cutoff = datetime.now() - timedelta(days=days)

    candidates = []
    for p in glob.glob(os.path.join("logs", "rename_partners_*.csv")):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(p))
            if mtime < cutoff:
                candidates.append(p)
        except Exception:
            continue

    if not candidates:
        return

    zip_name = os.path.join("logs", f"archive_{datetime.now().strftime('%Y-%m')}.zip")
    with zipfile.ZipFile(zip_name, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in candidates:
            arc = os.path.basename(p)
            if arc not in zf.namelist():
                zf.write(p, arcname=arc)
            try:
                os.remove(p)
            except Exception:
                pass


# ============================================================
# Parsing helpers
# ============================================================


def parse_processed_statuses(rename_mark: Any) -> Dict[int, str]:
    parsed = parse_rename_mark(rename_mark)
    return parsed.get("statuses", {})

# ============================================================
# MAIN
# ============================================================
def main():
    load_dotenv()

    sheet_id = (os.getenv("DIRECTORY_SHEET_ID", "") or "").strip()
    tab_name = (os.getenv("DIRECTORY_TAB_NAME", "") or "").strip()

    if not sheet_id or not tab_name:
        print(
            "Missing DIRECTORY_SHEET_ID / DIRECTORY_TAB_NAME in .env", file=sys.stderr
        )
        sys.exit(1)

    base_url = os.getenv("AFFILKA_BASE_URL", "").rstrip("/")
    op_email = os.getenv("AFFILKA_OPERATOR_EMAIL", "")
    op_pass = os.getenv("AFFILKA_OPERATOR_PASSWORD", "")
    totp_secret = os.getenv("AFFILKA_TOTP_SECRET", "")
    rpm = int(os.getenv("AFFILKA_RPM", "60"))

    if not base_url or not op_email or not op_pass or not totp_secret:
        print("Missing AFFILKA_* vars in .env", file=sys.stderr)
        sys.exit(1)

    archive_old_logs(days=int(os.getenv("LOG_ARCHIVE_AFTER_DAYS", "30")))

    log_path = make_run_log_path()
    f = open(log_path, "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "ts_utc",
            "sheet_row",
            "partner_id",
            "old_sheet_name",
            "target_name",
            "old_api_name",
            "action",
            "status",
            "note",
        ],
    )
    writer.writeheader()

    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(sheet_id)
        ws = open_worksheet_fuzzy(sh, tab_name)

        df = sheet_to_df(ws)
        if df.empty:
            print("Sheet is empty (no data rows).")
            return

        df = ensure_columns(
            df, [COL_PARTNER_ID, COL_OLD_NAME, COL_NEW_NAME, COL_RENAME]
        )

        client = ClientClient(base_url, op_email, op_pass, totp_secret, rpm=rpm)
        print("== Affilka login ==")
        client.login()

        rename_col_idx = list(df.columns).index(COL_RENAME)
        rename_col_letter = a1_col(rename_col_idx)

        updates_cells: List[str] = []
        updates_vals: List[List[str]] = []

        for i, row in df.iterrows():
            sheet_row = i + 2

            raw_ids = row.get(COL_PARTNER_ID, "")
            old_name = norm_str(row.get(COL_OLD_NAME, ""))
            target_name = norm_str(row.get(COL_NEW_NAME, ""))
            rename_mark = norm_str(row.get(COL_RENAME, ""))
            existing_statuses = parse_processed_statuses(rename_mark)

            if not target_name:
                log_print(
                    writer,
                    {
                        "ts_utc": utc_now().isoformat(),
                        "sheet_row": sheet_row,
                        "partner_id": "",
                        "old_sheet_name": old_name,
                        "target_name": "",
                        "old_api_name": "",
                        "action": "SKIP",
                        "status": "OK",
                        "note": "Partner Name is empty",
                    },
                )
                continue

            partner_ids = parse_partner_ids(raw_ids)
            if not partner_ids:
                log_print(
                    writer,
                    {
                        "ts_utc": utc_now().isoformat(),
                        "sheet_row": sheet_row,
                        "partner_id": "",
                        "old_sheet_name": old_name,
                        "target_name": target_name,
                        "old_api_name": "",
                        "action": "SKIP",
                        "status": "OK",
                        "note": "Partner ID is empty/invalid",
                    },
                )
                continue

            previous_target_name = ""
            if existing_statuses:
                previous_target_name = parse_rename_mark(rename_mark).get("target_name", "")

            pending_ids = [
                pid
                for pid in partner_ids
                if should_process_partner_id(existing_statuses.get(pid), target_name, previous_target_name)
            ]
            if not pending_ids:
                continue

            for pid in pending_ids:
                api_old = client.get_partner_name(pid)
                if api_old is None:
                    log_print(
                        writer,
                        {
                            "ts_utc": utc_now().isoformat(),
                            "sheet_row": sheet_row,
                            "partner_id": pid,
                            "old_sheet_name": old_name,
                            "target_name": target_name,
                            "old_api_name": "",
                            "action": "CHECK",
                            "status": "ERR",
                            "note": "Cannot fetch current name via API",
                        },
                    )
                    existing_statuses[pid] = "cannot_fetch"
                    continue

                if norm_str(api_old) == target_name:
                    log_print(
                        writer,
                        {
                            "ts_utc": utc_now().isoformat(),
                            "sheet_row": sheet_row,
                            "partner_id": pid,
                            "old_sheet_name": old_name,
                            "target_name": target_name,
                            "old_api_name": api_old,
                            "action": "NOOP",
                            "status": "OK",
                            "note": "Already has target name",
                        },
                    )
                    existing_statuses[pid] = "noop"
                    continue

                try:
                    client.rename_partner(pid, target_name)
                    api_now = client.get_partner_name(pid) or ""
                    ok = norm_str(api_now) == target_name

                    if ok:
                        log_print(
                            writer,
                            {
                                "ts_utc": utc_now().isoformat(),
                                "sheet_row": sheet_row,
                                "partner_id": pid,
                                "old_sheet_name": old_name,
                                "target_name": target_name,
                                "old_api_name": api_old,
                                "action": "RENAME",
                                "status": "OK",
                                "note": "Renamed",
                            },
                        )
                        existing_statuses[pid] = "renamed"
                    else:
                        log_print(
                            writer,
                            {
                                "ts_utc": utc_now().isoformat(),
                                "sheet_row": sheet_row,
                                "partner_id": pid,
                                "old_sheet_name": old_name,
                                "target_name": target_name,
                                "old_api_name": api_old,
                                "action": "RENAME",
                                "status": "WARN",
                                "note": f"Verify failed (now='{api_now}')",
                            },
                        )
                        existing_statuses[pid] = "verify_failed"
                except Exception as e:
                    log_print(
                        writer,
                        {
                            "ts_utc": utc_now().isoformat(),
                            "sheet_row": sheet_row,
                            "partner_id": pid,
                            "old_sheet_name": old_name,
                            "target_name": target_name,
                            "old_api_name": api_old,
                            "action": "RENAME",
                            "status": "ERR",
                            "note": str(e)[:800],
                        },
                    )
                    existing_statuses[pid] = "error"

            mark = build_rename_mark(target_name, existing_statuses)
            safe_mark = safe_csv_value(mark)

            updates_cells.append(f"{rename_col_letter}{sheet_row}")
            updates_vals.append([safe_mark])

        if updates_cells:
            ws.batch_update(
                [
                    {"range": rng, "values": [val]}
                    for rng, val in zip(updates_cells, updates_vals)
                ],
                value_input_option="RAW",
            )
            print(f"\nDONE ✅ Updated Rename marks: {len(updates_cells)} row(s)")
        else:
            print("\nDONE ✅ Nothing to update")

        print(f"Log: {log_path}")

    finally:
        try:
            f.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
