from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import pyotp
import requests
from requests.exceptions import (
    ConnectionError,
    ConnectTimeout,
    ReadTimeout,
    RequestException,
    SSLError,
)

try:
    import gspread
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.oauth2.credentials import Credentials as UserCredentials
    from google_auth_oauthlib.flow import InstalledAppFlow
except Exception:  # pragma: no cover - optional dependency for tests
    gspread = None
    UserCredentials = None
    InstalledAppFlow = None
    GoogleAuthRequest = None


SUCCESS_STATUSES: Set[str] = {"renamed", "noop"}
RETRY_STATUSES: Set[str] = {"error", "cannot_fetch", "verify_failed"}
ID_TOKEN_RE = re.compile(r"\d+")
STATUS_TOKEN_RE = re.compile(r"(\d+):(noop|renamed|error|cannot_fetch|verify_failed)")


class PartnerPlatformClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        totp_secret: str,
        rpm: int = 60,
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

    def _rate(self) -> None:
        now = time.time()
        dt = now - self._last
        if dt < self.min_interval:
            time.sleep(self.min_interval - dt)
        self._last = time.time()

    def _totp_now(self) -> str:
        return pyotp.TOTP(self.totp_secret).now()

    def login(self) -> None:
        url = f"{self.base_url}/api/client/casino/sign_in"
        last_err: Optional[Exception] = None
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
            last_err = RuntimeError(f"LOGIN expected 201, got {r.status_code}\n{r.text[:2000]}")
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
        params: Optional[List[Tuple[str, Any]]] = None,
        json_body: Any = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        max_attempts = 10
        backoff = 3.0
        timeout = (25, 240)

        for attempt in range(1, max_attempts + 1):
            self._rate()
            try:
                r = self.session.request(method, url, params=params, json=json_body, timeout=timeout)
            except (ReadTimeout, ConnectTimeout, SSLError, ConnectionError, RequestException) as e:
                print(f"[client net] {type(e).__name__}: retry {backoff:.1f}s ({attempt}/{max_attempts})")
                time.sleep(backoff)
                backoff = min(backoff * 1.7, 180)
                continue

            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                wait_s = float(ra) if ra and ra.replace(".", "", 1).isdigit() else backoff
                print(f"[client 429] wait {wait_s:.1f}s ({attempt}/{max_attempts})")
                time.sleep(min(wait_s, 180))
                backoff = min(backoff * 1.7, 180)
                continue

            if 500 <= r.status_code <= 599:
                print(f"[client {r.status_code}] wait {backoff:.1f}s ({attempt}/{max_attempts})")
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
                    "GET",
                    "/api/client/casino/partners",
                    params=[("page", page)],
                )
            except Exception:
                return None

            items = data.get("items") if isinstance(data, dict) else None
            if not items:
                return None

            for item in items:
                try:
                    if int(item.get("id")) == int(partner_id):
                        return item.get("name")
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


class GoogleOAuthClient:
    def __init__(self, auth_mode: str = "oauth", creds_path: str = "credentials.json", token_path: str = "token.json"):
        self.auth_mode = (auth_mode or "oauth").strip().lower()
        self.creds_path = creds_path
        self.token_path = token_path
        self.scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]

    def get_client(self) -> Any:
        if self.auth_mode != "oauth":
            raise RuntimeError("Expected GOOGLE_AUTH_MODE=oauth.")
        if gspread is None or UserCredentials is None or InstalledAppFlow is None or GoogleAuthRequest is None:
            raise RuntimeError("Google dependencies are not available.")

        creds: Optional[Any] = None
        if os.path.exists(self.token_path):
            creds = UserCredentials.from_authorized_user_file(self.token_path, self.scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(GoogleAuthRequest())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.creds_path, self.scopes)
                creds = flow.run_local_server(port=0)
            with open(self.token_path, "w", encoding="utf-8") as handle:
                handle.write(creds.to_json())

        return gspread.authorize(creds)


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
            continue
    seen = set()
    res = []
    for item in out:
        if item not in seen:
            seen.add(item)
            res.append(item)
    return res


def norm_str(v: Any) -> str:
    return "" if v is None else str(v).strip()


def parse_rename_mark(mark: Any) -> Dict[str, Any]:
    text = norm_str(mark)
    if not text:
        return {"target_name": "", "statuses": {}}

    target_name = ""
    statuses: Dict[int, str] = {}

    structured_match = re.search(r"target='([^']*)'\s*\|\s*statuses=(.*)$", text)
    if structured_match:
        target_name = structured_match.group(1)
        raw_statuses = structured_match.group(2)
        for match in STATUS_TOKEN_RE.finditer(raw_statuses):
            statuses[int(match.group(1))] = match.group(2)
        return {"target_name": target_name, "statuses": statuses}

    legacy_match = re.search(r"target='([^']*)'", text)
    if legacy_match:
        target_name = legacy_match.group(1)

    for match in STATUS_TOKEN_RE.finditer(text):
        statuses[int(match.group(1))] = match.group(2)

    return {"target_name": target_name, "statuses": statuses}


def build_rename_mark(target_name: str, statuses: Dict[int, str]) -> str:
    if not statuses:
        return ""
    ordered = sorted(statuses.keys())
    pieces = [f"{pid}:{statuses[pid]}" for pid in ordered]
    return f"target='{target_name}' | statuses={','.join(pieces)}"


def is_success_status(status: Optional[str]) -> bool:
    return bool(status and status in SUCCESS_STATUSES)


def should_process_partner_id(status: Optional[str], target_name: str, previous_target_name: str) -> bool:
    if previous_target_name and target_name != previous_target_name:
        return True
    if not status:
        return True
    return status not in SUCCESS_STATUSES


def safe_csv_value(value: Any) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def validate_required_columns(df: Any, required_columns: List[str], sheet_name: str) -> None:
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        available = list(df.columns)
        raise ValueError(
            f"Missing required columns for sheet '{sheet_name}': {missing}. Found: {available}"
        )


def validate_affilka_base_url(base_url: str, allowed_hosts: Optional[Set[str]] = None) -> str:
    parsed = urlparse(base_url or "")
    if parsed.scheme != "https":
        raise ValueError("AFFILKA_BASE_URL must use https scheme.")
    if not parsed.hostname:
        raise ValueError("AFFILKA_BASE_URL must include a hostname.")
    if parsed.username or parsed.password:
        raise ValueError("AFFILKA_BASE_URL must not include username or password.")
    allowed = {host.lower() for host in (allowed_hosts or set())}
    if allowed and parsed.hostname.lower() not in allowed:
        raise ValueError(
            f"AFFILKA_BASE_URL hostname '{parsed.hostname}' is not in AFFILKA_ALLOWED_HOSTS."
        )
    return base_url.rstrip("/")


ClientClient = PartnerPlatformClient
