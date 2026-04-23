import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
import pandas as pd
import pyotp
from dotenv import load_dotenv

import gspread
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleAuthRequest

from requests.exceptions import (
    ReadTimeout,
    ConnectTimeout,
    SSLError,
    ConnectionError,
    RequestException,
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


def get_gspread_client() -> gspread.Client:
    mode = (os.getenv("GOOGLE_AUTH_MODE", "oauth") or "oauth").strip().lower()
    if mode != "oauth":
        raise RuntimeError("Expected GOOGLE_AUTH_MODE=oauth.")

    creds_path = os.getenv("GOOGLE_OAUTH_CLIENT_FILE", "credentials.json")
    token_path = os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "token.json")

    creds: Optional[UserCredentials] = None
    if os.path.exists(token_path):
        creds = UserCredentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleAuthRequest())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return gspread.authorize(creds)


def sheet_to_df(ws: gspread.Worksheet) -> pd.DataFrame:
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


def a1_col(col_idx_0_based: int) -> str:
    n = col_idx_0_based + 1
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def norm_str(v: Any) -> str:
    return "" if v is None else str(v).strip()


ID_TOKEN_RE = re.compile(r"\d+")


def parse_partner_ids(raw: Any) -> List[int]:
    if raw is None:
        return []
    s = str(raw).strip()
    if not s:
        return []
    nums = ID_TOKEN_RE.findall(s)
    out: List[int] = []
    for n in nums:
        try:
            out.append(int(n))
        except Exception:
            pass
    seen = set()
    res = []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


# ============================================================
# Affilka client
# ============================================================
ParamsType = List[Tuple[str, Any]]


class ClientClient:
    def __init__(
        self, base_url: str, email: str, password: str, totp_secret: str, rpm: int = 60
    ):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.totp_secret = totp_secret
        self.session = requests.Session()
        self.session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )
        self.min_interval = 60.0 / max(1, rpm)
        self._last = 0.0

    def _rate(self):
        now = time.time()
        dt = now - self._last
        if dt < self.min_interval:
            time.sleep(self.min_interval - dt)
        self._last = time.time()

    def _totp_now(self) -> str:
        return pyotp.TOTP(self.totp_secret).now()

    def login(self) -> None:
        url = f"{self.base_url}/api/client/casino/sign_in"
        last_err = None
        for _ in range(2):
            payload = {
                "casino_user": {
                    "email": self.email,
                    "password": self.password,
                    "otp_attempt": str(self._totp_now()),
                }
            }
            r = self.session.post(url, json=payload, timeout=(20, 180))
            if r.status_code == 201:
                last_err = None
                break
            last_err = RuntimeError(
                f"LOGIN expected 201, got {r.status_code}\n{r.text[:2000]}"
            )
            time.sleep(1.0)
        if last_err:
            raise last_err

        me_url = f"{self.base_url}/api/client/casino/current_user"
        me = self.session.get(me_url, timeout=(20, 180))
        if me.status_code != 200:
            raise RuntimeError(
                f"current_user expected 200, got {me.status_code}\n{me.text[:2000]}"
            )

        csrf = (
            self.session.cookies.get("CSRF-TOKEN")
            or self.session.cookies.get("XSRF-TOKEN")
            or self.session.cookies.get("csrf_token")
        )
        if not csrf:
            raise RuntimeError("CSRF cookie not found after current_user.")
        self.session.headers["X-CSRF-Token"] = csrf
        self.session.headers["X-CSRF-TOKEN"] = csrf

    def request_json(
        self,
        method: str,
        path: str,
        params: Optional[ParamsType] = None,
        json_body: Any = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        max_attempts = 10
        backoff = 3.0
        timeout = (25, 240)

        for attempt in range(1, max_attempts + 1):
            self._rate()
            try:
                r = self.session.request(
                    method, url, params=params, json=json_body, timeout=timeout
                )
            except (
                ReadTimeout,
                ConnectTimeout,
                SSLError,
                ConnectionError,
                RequestException,
            ) as e:
                print(
                    f"[client net] {type(e).__name__}: retry {backoff:.1f}s ({attempt}/{max_attempts})"
                )
                time.sleep(backoff)
                backoff = min(backoff * 1.7, 180)
                continue

            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                wait_s = (
                    float(ra) if ra and ra.replace(".", "", 1).isdigit() else backoff
                )
                print(f"[client 429] wait {wait_s:.1f}s ({attempt}/{max_attempts})")
                time.sleep(min(wait_s, 180))
                backoff = min(backoff * 1.7, 180)
                continue

            if 500 <= r.status_code <= 599:
                print(
                    f"[client {r.status_code}] wait {backoff:.1f}s ({attempt}/{max_attempts})"
                )
                time.sleep(backoff)
                backoff = min(backoff * 1.7, 180)
                continue

            if r.status_code == 204:
                return {}

            if r.status_code < 200 or r.status_code >= 300:
                raise RuntimeError(f"HTTP {r.status_code} for {url}\n{r.text[:2000]}")

            if not r.text.strip():
                return {}
            return r.json()

        raise RuntimeError(f"Client failed too many retries for {url}")

    def get_partner_name(self, partner_id: int) -> Optional[str]:
        try:
            data = self.request_json("GET", f"/api/client/casino/partners/{partner_id}")
            if isinstance(data, dict):
                if "partner" in data and isinstance(data["partner"], dict):
                    return data["partner"].get("name")
                if "name" in data:
                    return data.get("name")
        except Exception:
            pass

        page = 1
        for _ in range(1, 400):
            try:
                data = self.request_json(
                    "GET", "/api/client/casino/partners", params=[("page", page)]
                )
            except Exception:
                return None

            items = data.get("items") if isinstance(data, dict) else None
            if not items:
                return None

            for it in items:
                try:
                    if int(it.get("id")) == int(partner_id):
                        return it.get("name")
                except Exception:
                    continue

            total_pages = int(data.get("total_pages") or page)
            if page >= total_pages:
                return None
            page += 1

        return None



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
        updates_vals.append([target_name])
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
