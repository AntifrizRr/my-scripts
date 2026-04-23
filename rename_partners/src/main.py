import os
import re
import sys
import csv
import time
import glob
import zipfile
from datetime import datetime, timezone, timedelta
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
# Columns in DIRECTORY_TAB
# ============================================================
COL_PARTNER_ID = "Partner ID"
COL_OLD_NAME = "OLD name"
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
# Affilka client (operator login + CSRF)
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
        # try direct
        try:
            data = self.request_json("GET", f"/api/client/casino/partners/{partner_id}")
            if isinstance(data, dict):
                if "partner" in data and isinstance(data["partner"], dict):
                    return data["partner"].get("name")
                if "name" in data:
                    return data.get("name")
        except Exception:
            pass

        # fallback list
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

    def rename_partner(self, partner_id: int, new_name: str) -> None:
        self.request_json(
            "PUT",
            f"/api/client/casino/partners/{partner_id}",
            json_body={"partner": {"name": new_name}},
        )


# ============================================================
# Parsing helpers
# ============================================================
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


def norm_str(v: Any) -> str:
    return "" if v is None else str(v).strip()



STATUS_TOKEN_RE = re.compile(r"(\d+):(noop|renamed|error|cannot_fetch)")

def parse_processed_statuses(rename_mark: Any) -> Dict[int, str]:
    """
    Parse existing Rename cell text like:
      RENAMED ... | 123:renamed,456:noop,789:error
    Returns {123: "renamed", 456: "noop", 789: "error"}.
    """
    s = norm_str(rename_mark)
    out: Dict[int, str] = {}
    if not s:
        return out
    for m in STATUS_TOKEN_RE.finditer(s):
        try:
            out[int(m.group(1))] = m.group(2)
        except Exception:
            continue
    return out

def build_rename_mark(target_name: str, statuses: Dict[int, str]) -> str:
    """
    Rebuild Rename mark from per-ID statuses.
    Success statuses: renamed, noop
    Error statuses: error, cannot_fetch
    """
    if not statuses:
        return ""
    order = sorted(statuses.keys())
    notes = ",".join(f"{pid}:{statuses[pid]}" for pid in order)
    has_error = any(v in {"error", "cannot_fetch"} for v in statuses.values())
    prefix = "ERROR" if has_error else "RENAMED"
    return f"{prefix} {utc_now().isoformat()} | target='{target_name}' | " + notes

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

            # Process only IDs that are not already present in Rename status.
            # This fixes the case when new IDs are later added into the same cell.
            pending_ids = [pid for pid in partner_ids if pid not in existing_statuses]
            if not pending_ids:
                continue

            any_success = any(v in {"renamed", "noop"} for v in existing_statuses.values())

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
                    any_success = True
                    existing_statuses[pid] = "noop"
                    continue

                try:
                    client.rename_partner(pid, target_name)
                    api_now = client.get_partner_name(pid) or ""
                    ok = norm_str(api_now) == target_name

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
                            "status": "OK" if ok else "WARN",
                            "note": (
                                "Renamed"
                                if ok
                                else f"Renamed but verify failed (now='{api_now}')"
                            ),
                        },
                    )
                    any_success = True
                    existing_statuses[pid] = "renamed"
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

            updates_cells.append(f"{rename_col_letter}{sheet_row}")
            updates_vals.append([mark])

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
