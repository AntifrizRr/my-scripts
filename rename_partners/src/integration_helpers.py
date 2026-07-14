from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlparse

import pyotp
import requests
from requests.exceptions import RequestException

try:
    import gspread
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.oauth2.credentials import Credentials as UserCredentials
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:  # pragma: no cover - optional during isolated unit tests
    gspread = None
    GoogleAuthRequest = None
    UserCredentials = None
    InstalledAppFlow = None


SUCCESS_STATUSES: Set[str] = {"renamed", "noop"}
ID_TOKEN_RE = re.compile(r"\d+")
STATUS_TOKEN_RE = re.compile(
    r"(\d+):(noop|renamed|error|cannot_fetch|verify_failed)"
)


class PartnerPlatformClient:
    """Small HTTP client for the partner-name workflow."""

    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        totp_secret: str,
        rpm: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.totp_secret = totp_secret
        self.session = requests.Session()
        self.session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )
        self.min_interval = 60.0 / max(1, rpm)
        self._last_request_at = 0.0

    def _wait_for_rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_at = time.time()

    def _totp_now(self) -> str:
        return pyotp.TOTP(self.totp_secret).now()

    def login(self) -> None:
        sign_in_url = f"{self.base_url}/api/client/casino/sign_in"
        last_error: Optional[Exception] = None

        for _ in range(2):
            payload = {
                "casino_user": {
                    "email": self.email,
                    "password": self.password,
                    "otp_attempt": self._totp_now(),
                }
            }
            response = self.session.post(
                sign_in_url,
                json=payload,
                timeout=(20, 180),
            )
            if response.status_code == 201:
                last_error = None
                break

            last_error = RuntimeError(
                f"Login expected HTTP 201, got {response.status_code}: "
                f"{response.text[:1000]}"
            )
            time.sleep(1.0)

        if last_error:
            raise last_error

        current_user_url = f"{self.base_url}/api/client/casino/current_user"
        response = self.session.get(current_user_url, timeout=(20, 180))
        if response.status_code != 200:
            raise RuntimeError(
                f"Current user expected HTTP 200, got {response.status_code}: "
                f"{response.text[:1000]}"
            )

        csrf_token = (
            self.session.cookies.get("CSRF-TOKEN")
            or self.session.cookies.get("XSRF-TOKEN")
            or self.session.cookies.get("csrf_token")
        )
        if not csrf_token:
            raise RuntimeError("CSRF cookie was not found after login.")

        self.session.headers["X-CSRF-Token"] = csrf_token
        self.session.headers["X-CSRF-TOKEN"] = csrf_token

    def request_json(
        self,
        method: str,
        path: str,
        params: Optional[List[Tuple[str, Any]]] = None,
        json_body: Any = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        max_attempts = 10
        backoff_seconds = 3.0

        for attempt in range(1, max_attempts + 1):
            self._wait_for_rate_limit()

            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    timeout=(25, 240),
                )
            except RequestException as exc:
                if attempt == max_attempts:
                    raise RuntimeError(
                        f"Request failed after {max_attempts} attempts: {url}"
                    ) from exc
                print(
                    f"[network] {type(exc).__name__}; retry in "
                    f"{backoff_seconds:.1f}s ({attempt}/{max_attempts})"
                )
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 1.7, 180)
                continue

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "")
                wait_seconds = (
                    float(retry_after)
                    if retry_after.replace(".", "", 1).isdigit()
                    else backoff_seconds
                )
                time.sleep(min(wait_seconds, 180))
                backoff_seconds = min(backoff_seconds * 1.7, 180)
                continue

            if 500 <= response.status_code <= 599:
                if attempt == max_attempts:
                    raise RuntimeError(
                        f"HTTP {response.status_code} after "
                        f"{max_attempts} attempts: {url}"
                    )
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 1.7, 180)
                continue

            if response.status_code == 204 or not response.text.strip():
                return {}

            if not 200 <= response.status_code < 300:
                raise RuntimeError(
                    f"HTTP {response.status_code} for {url}: "
                    f"{response.text[:1000]}"
                )

            data = response.json()
            return data if isinstance(data, dict) else {"data": data}

        raise RuntimeError(f"Request failed after {max_attempts} attempts: {url}")

    def get_partner_name(self, partner_id: int) -> Optional[str]:
        try:
            data = self.request_json(
                "GET",
                f"/api/client/casino/partners/{partner_id}",
            )
            partner = data.get("partner")
            if isinstance(partner, dict):
                return partner.get("name")
            if "name" in data:
                return data.get("name")
        except Exception:
            pass

        page = 1
        for _ in range(400):
            try:
                data = self.request_json(
                    "GET",
                    "/api/client/casino/partners",
                    params=[("page", page)],
                )
            except Exception:
                return None

            items = data.get("items")
            if not isinstance(items, list) or not items:
                return None

            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    if int(item.get("id")) == int(partner_id):
                        return item.get("name")
                except (TypeError, ValueError):
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
    def __init__(
        self,
        auth_mode: str = "oauth",
        creds_path: str = "credentials.json",
        token_path: str = "token.json",
    ) -> None:
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
        if (
            gspread is None
            or UserCredentials is None
            or InstalledAppFlow is None
            or GoogleAuthRequest is None
        ):
            raise RuntimeError("Google dependencies are not available.")

        credentials: Optional[Any] = None
        if os.path.exists(self.token_path):
            credentials = UserCredentials.from_authorized_user_file(
                self.token_path,
                self.scopes,
            )

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(GoogleAuthRequest())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.creds_path,
                    self.scopes,
                )
                credentials = flow.run_local_server(port=0)

            with open(self.token_path, "w", encoding="utf-8") as handle:
                handle.write(credentials.to_json())

        return gspread.authorize(credentials)


def parse_partner_ids(raw: Any) -> List[int]:
    if raw is None:
        return []

    numbers = ID_TOKEN_RE.findall(str(raw).strip())
    result: List[int] = []
    seen: Set[int] = set()

    for number in numbers:
        partner_id = int(number)
        if partner_id not in seen:
            seen.add(partner_id)
            result.append(partner_id)

    return result


def norm_str(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_rename_mark(mark: Any) -> Dict[str, Any]:
    text = norm_str(mark)
    if not text:
        return {"target_name": "", "statuses": {}}

    target_match = re.search(r"target='([^']*)'", text)
    target_name = target_match.group(1) if target_match else ""

    statuses: Dict[int, str] = {}
    for match in STATUS_TOKEN_RE.finditer(text):
        statuses[int(match.group(1))] = match.group(2)

    return {"target_name": target_name, "statuses": statuses}


def build_rename_mark(target_name: str, statuses: Dict[int, str]) -> str:
    if not statuses:
        return ""

    status_items = ",".join(
        f"{partner_id}:{statuses[partner_id]}"
        for partner_id in sorted(statuses)
    )
    return f"target='{target_name}' | statuses={status_items}"


def is_success_status(status: Optional[str]) -> bool:
    return bool(status and status in SUCCESS_STATUSES)


def should_process_partner_id(
    status: Optional[str],
    target_name: str,
    previous_target_name: str,
) -> bool:
    if previous_target_name and target_name != previous_target_name:
        return True
    return not is_success_status(status)


def successful_partner_ids(
    rename_mark: Any,
    partner_ids: Iterable[int],
) -> Set[int]:
    """Return IDs that can be used by the follow-up synchronization.

    Structured marks use per-ID statuses. Legacy marks beginning with
    ``RENAMED`` are accepted for compatibility with older spreadsheet rows.
    """

    ids = set(partner_ids)
    text = norm_str(rename_mark)
    parsed = parse_rename_mark(text)
    statuses = parsed.get("statuses", {})

    if statuses:
        return {
            partner_id
            for partner_id in ids
            if is_success_status(statuses.get(partner_id))
        }

    if text.upper().startswith("RENAMED"):
        return ids

    return set()


def safe_csv_value(value: Any) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def validate_required_columns(
    dataframe: Any,
    required_columns: List[str],
    sheet_name: str,
) -> None:
    missing = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]
    if missing:
        raise ValueError(
            f"Missing required columns for sheet '{sheet_name}': {missing}. "
            f"Found: {list(dataframe.columns)}"
        )


def parse_allowed_hosts(raw: str) -> Set[str]:
    return {
        host.strip().lower()
        for host in (raw or "").split(",")
        if host.strip()
    }


def validate_partner_base_url(
    base_url: str,
    allowed_hosts: Optional[Set[str]] = None,
) -> str:
    parsed = urlparse(base_url or "")

    if parsed.scheme != "https":
        raise ValueError("Partner API base URL must use HTTPS.")
    if not parsed.hostname:
        raise ValueError("Partner API base URL must include a hostname.")
    if parsed.username or parsed.password:
        raise ValueError(
            "Partner API base URL must not include a username or password."
        )

    normalized_allowed_hosts = {
        host.lower()
        for host in (allowed_hosts or set())
    }
    if (
        normalized_allowed_hosts
        and parsed.hostname.lower() not in normalized_allowed_hosts
    ):
        raise ValueError(
            f"Partner API hostname '{parsed.hostname}' is not in "
            "AFFILKA_ALLOWED_HOSTS."
        )

    return base_url.rstrip("/")
