from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests


@dataclass(frozen=True)
class Credentials:
    email: str
    password: str


class WQError(RuntimeError):
    pass


class ThrottledError(WQError):
    pass


class UnsupportedOperatorError(WQError):
    def __init__(self, operator_name: str, attempted: tuple[str, ...], message: str):
        super().__init__(message)
        self.operator_name = operator_name
        self.attempted = attempted


_UNKNOWN_OPERATOR_RE = __import__("re").compile(r'unknown operator\s+"(?P<op>[^"]+)"', __import__("re").IGNORECASE)


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return None


def _sleep_seconds_from_response(resp: requests.Response, default_seconds: float) -> float:
    try:
        ra = resp.headers.get("Retry-After")
        if ra is None:
            return default_seconds
        return max(float(ra), default_seconds)
    except Exception:
        return default_seconds


class WQClient(requests.Session):
    def __init__(self, credentials_path: Path):
        super().__init__()
        self._credentials_path = credentials_path
        self._creds = self._load_credentials(credentials_path)
        self.auth = (self._creds.email, self._creds.password)
        self._login()

    @staticmethod
    def _load_credentials(path: Path) -> Credentials:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Credentials(email=data["email"], password=data["password"])

    def _login(self) -> None:
        r = self._request_with_retry("POST", "https://api.worldquantbrain.com/authentication")
        j = _safe_json(r)
        if not isinstance(j, dict) or "user" not in j:
            # Some accounts may require interactive biometric flow; keep message explicit.
            raise WQError(f"Login failed or requires interactive verification: {str(j)[:500]}")

    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        max_attempts = int(kwargs.pop("_max_attempts", 20))
        base_sleep = float(kwargs.pop("_base_sleep", 2.0))

        sleep_seconds = base_sleep
        last_exc: Optional[BaseException] = None

        for _ in range(max_attempts):
            try:
                resp = super().request(method, url, timeout=60, **kwargs)

                if resp.status_code == 429:
                    time.sleep(_sleep_seconds_from_response(resp, sleep_seconds))
                    sleep_seconds = min(sleep_seconds * 1.5, 60.0)
                    continue

                if 500 <= resp.status_code <= 599:
                    time.sleep(sleep_seconds)
                    sleep_seconds = min(sleep_seconds * 1.5, 60.0)
                    continue

                return resp
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(sleep_seconds)
                sleep_seconds = min(sleep_seconds * 1.5, 60.0)

        if last_exc:
            raise last_exc
        raise WQError("request retry exceeded")

    def create_simulation(self, *, formula: str, settings: dict[str, Any]) -> str:
        r = self._request_with_retry(
            "POST",
            "https://api.worldquantbrain.com/simulations",
            json={"regular": formula, "type": "REGULAR", "settings": settings},
        )
        if r.status_code == 429:
            raise ThrottledError("Throttled (HTTP 429) when creating simulation")
        if r.status_code >= 400:
            j = _safe_json(r)
            msg = None
            if isinstance(j, dict):
                msg = j.get("message") or j.get("detail")
            raise WQError(f"Simulation create failed: HTTP {r.status_code} {msg or r.text[:500]}")

        sim_url = r.headers.get("Location")
        if not sim_url:
            raise WQError("Simulation response missing Location header")
        return sim_url

    def poll_simulation(self, *, sim_url: str, poll_seconds: float) -> str:
        while True:
            time.sleep(poll_seconds)
            r = self._request_with_retry("GET", sim_url)
            if r.status_code == 429:
                continue
            j = _safe_json(r)
            if not isinstance(j, dict):
                raise WQError(f"Unexpected simulation poll response: HTTP {r.status_code}")

            if "alpha" in j:
                return str(j["alpha"])

            if "progress" in j:
                continue

            if "message" in j:
                raise WQError(f"Simulation error: {j['message']}")

            raise WQError(f"Unexpected simulation state: {str(j)[:300]}")

    def fetch_alpha(self, alpha_platform_id: str) -> dict[str, Any]:
        r = self._request_with_retry("GET", f"https://api.worldquantbrain.com/alphas/{alpha_platform_id}")
        if r.status_code >= 400:
            raise WQError(f"Alpha fetch failed: HTTP {r.status_code} {r.text[:500]}")
        j = _safe_json(r)
        if not isinstance(j, dict):
            raise WQError("Alpha fetch returned non-JSON")
        return j


def extract_unknown_operator(message: str) -> Optional[str]:
    m = _UNKNOWN_OPERATOR_RE.search(message or "")
    if not m:
        return None
    return m.group("op")


def rewrite_operator(formula: str, *, old: str, new: str) -> str:
    import re

    return re.sub(rf"\b{re.escape(old)}\b", new, formula)
