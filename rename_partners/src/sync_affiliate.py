import os
import re
import sys
from typing import Dict, List

import gspread
import pandas as pd
from dotenv import load_dotenv

from .portfolio_shared import (
    ClientClient,
    GoogleOAuthClient,
    norm_str,
    parse_partner_ids,
    safe_csv_value,
    validate_required_columns,
)

# ============================================================
# DIRECTORY (same sheet)
# ============================================================
COL_PARTNER_ID = "Partner ID"
COL_NEW_NAME = "Partner Name"
COL_RENAME = "Rename"

# ============================================================
# Google OAuth
# ============================================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


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


def _chunks(seq, size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i+size]

def main():
    load_dotenv()

    # Plan_Fact target (same sheet/tab in твоём случае)
    plan_sheet_id = (os.getenv("PLAN_FACT_SHEET_ID", "") or "").strip()
    plan_tab = (os.getenv("PLAN_FACT_TAB_NAME", "") or "").strip()
    col_aff_id = (os.getenv("PLAN_FACT_COL_AFF_ID", "Affiliate ID") or "").strip()
    col_aff_name = (os.getenv("PLAN_FACT_COL_AFF_NAME", "Affiliate") or "").strip()

    # Directory source
    dir_sheet_id = (os.getenv("DIRECTORY_SHEET_ID", "") or "").strip()
    dir_tab = (os.getenv("DIRECTORY_TAB_NAME", "") or "").strip()

    if not plan_sheet_id or not plan_tab or not dir_sheet_id or not dir_tab:
        print("Missing PLAN_FACT_* or DIRECTORY_* in .env", file=sys.stderr)
        sys.exit(1)

    base_url = os.getenv("AFFILKA_BASE_URL", "").rstrip("/")
    op_email = os.getenv("AFFILKA_OPERATOR_EMAIL", "")
    op_pass = os.getenv("AFFILKA_OPERATOR_PASSWORD", "")
    totp_secret = os.getenv("AFFILKA_TOTP_SECRET", "")
    rpm = int(os.getenv("AFFILKA_RPM", "60"))

    if not base_url or not op_email or not op_pass or not totp_secret:
        print("Missing AFFILKA_* vars in .env", file=sys.stderr)
        sys.exit(1)

    gc = get_gspread_client()

    # Read directory and build mapping ONLY for rows that have Rename mark
    sh_dir = gc.open_by_key(dir_sheet_id)
    ws_dir = open_worksheet_fuzzy(sh_dir, dir_tab)
    df_dir = sheet_to_df(ws_dir)
    df_dir = ensure_columns(df_dir, [COL_PARTNER_ID, COL_NEW_NAME, COL_RENAME])
    ensure_required_columns(df_dir, [COL_PARTNER_ID, COL_NEW_NAME, COL_RENAME], "Directory")

    mapping: Dict[int, str] = {}
    for _, r in df_dir.iterrows():
        rm = norm_str(r.get(COL_RENAME, ""))
        if not rm.startswith("RENAMED"):
            continue
        target = norm_str(r.get(COL_NEW_NAME, ""))
        if not target:
            continue
        ids = parse_partner_ids(r.get(COL_PARTNER_ID, ""))
        for pid in ids:
            mapping[pid] = target

    if not mapping:
        print("Nothing to sync: no rows with Rename mark in directory sheet.")
        return

    # Affilka
    client = ClientClient(base_url, op_email, op_pass, totp_secret, rpm=rpm)
    print("== Affilka login ==")
    client.login()

    # Open Plan_Fact (same tab)
    sh_pf = gc.open_by_key(plan_sheet_id)
    ws_pf = open_worksheet_fuzzy(sh_pf, plan_tab)
    df_pf = sheet_to_df(ws_pf)
    if df_pf.empty:
        print("Target sheet is empty.")
        return

    df_pf = ensure_columns(df_pf, [col_aff_id, col_aff_name])
    ensure_required_columns(df_pf, [col_aff_id, col_aff_name], plan_tab)

    aff_name_idx = list(df_pf.columns).index(col_aff_name)
    aff_name_letter = a1_col(aff_name_idx)

    already_ok = 0
    api_mismatch = 0
    cannot_fetch = 0
    no_mapping = 0

    updates_cells: List[str] = []
    updates_vals: List[List[str]] = []

    checked = 0
    changed = 0

    for i, row in df_pf.iterrows():
        sheet_row = i + 2

        raw_aff_id = norm_str(row.get(col_aff_id, ""))
        if not raw_aff_id:
            continue

        ids = parse_partner_ids(raw_aff_id)
        if not ids:
            continue

        pid = ids[0]
        target_name = mapping.get(pid)
        if not target_name:
            no_mapping += 1
            continue

        # API check: update only if current partner name == target_name
        api_name = client.get_partner_name(pid)
        checked += 1
        if api_name is None:
            cannot_fetch += 1
            print(f"[skip] row={sheet_row} pid={pid}: cannot fetch current name")
            continue

        if norm_str(api_name) != target_name:
            api_mismatch += 1
            print(
                f"[skip] row={sheet_row} pid={pid}: current='{api_name}' != target='{target_name}'"
            )
            continue

        cur_aff = norm_str(row.get(col_aff_name, ""))
        if cur_aff == target_name:
            already_ok += 1
            print(
                f"[noop] row={sheet_row} pid={pid}: Affiliate already '{target_name}'"
            )
            continue

        updates_cells.append(f"{aff_name_letter}{sheet_row}")
        updates_vals.append([safe_csv_value(target_name)])
        changed += 1
        print(
            f"[update] row={sheet_row} pid={pid} affiliate='{cur_aff}' -> '{target_name}'"
        )

    if updates_cells:
        # Google API doesn't accept list of A1 cells in ws.update(); use batch_update per-cell (chunked).
        for batch in _chunks(list(zip(updates_cells, updates_vals)), 500):
            ws_pf.batch_update(
                [{"range": rng, "values": [val]} for rng, val in batch],
                value_input_option="RAW",
            )

    print("\nDONE ✅")
    print(f"- mapping size: {len(mapping)}")
    print(f"- checked via API: {checked}")
    print(f"- updated cells: {changed}")
    print(f"- already_ok: {already_ok}")
    print(f"- api_mismatch: {api_mismatch}")
    print(f"- cannot_fetch: {cannot_fetch}")
    print(f"- no_mapping: {no_mapping}")


if __name__ == "__main__":
    main()
