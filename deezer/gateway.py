"""Authenticated session and the gw-light JSON gateway."""

from __future__ import annotations

import json
import time

import requests

from .constants import GW, UA
from .errors import DeezerError


class Gateway:
    def __init__(self, arl: str) -> None:
        self.arl = arl.strip()
        self._session: requests.Session | None = None
        self.check = "null"
        self.license = ""
        self.user_id = 0
        self.user = ""
        self.tier = "free"
        self.country = ""
        self.login()

    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(
                {"User-Agent": UA, "Origin": "https://www.deezer.com", "Referer": "https://www.deezer.com/"}
            )
            self._session.cookies.update({"arl": self.arl, "comeback": "1"})
        return self._session

    def login(self) -> None:
        params = {"api_version": "1.0", "api_token": "null", "input": "3", "method": "deezer.getUserData"}
        try:
            response = self.session().post(GW, params=params, json={}, timeout=30)
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DeezerError(f"login: {exc}") from exc
        if not isinstance(payload, dict):
            raise DeezerError("login: unexpected reply from gateway")
        results = payload.get("results") or {}
        user = results.get("USER") or {}
        if not user.get("USER_ID"):
            raise DeezerError("ARL rejected or expired")
        options = user.get("OPTIONS") or {}
        self.check = results.get("checkForm") or "null"
        self.license = options.get("license_token") or ""
        self.user_id = int(user["USER_ID"])
        self.user = user.get("BLOG_NAME") or str(self.user_id)
        self.country = options.get("license_country") or ""
        if options.get("web_lossless"):
            self.tier = "lossless"
        elif options.get("web_hq"):
            self.tier = "high"
        else:
            self.tier = "free"

    def call(self, method: str, data: dict | None = None, retries: int = 3) -> dict:
        params = {"api_version": "1.0", "api_token": self.check, "input": "3", "method": method}
        for attempt in range(retries):
            try:
                response = self.session().post(GW, params=params, json=data or {}, timeout=30)
            except requests.RequestException as exc:
                if attempt + 1 == retries:
                    raise DeezerError(f"{method}: {exc}") from exc
                time.sleep(1.5 * (attempt + 1))
                continue

            if response.status_code in (429, 500, 502, 503, 504):
                if attempt + 1 == retries:
                    raise DeezerError(f"{method}: HTTP {response.status_code}")
                time.sleep(2.0 * (attempt + 1))
                continue

            try:
                payload = response.json()
            except ValueError as exc:
                raise DeezerError(f"{method}: HTTP {response.status_code}, non-JSON reply") from exc
            if not isinstance(payload, dict):
                raise DeezerError(f"{method}: unexpected reply from gateway")

            error = payload.get("error")
            if error:
                message = error if isinstance(error, str) else json.dumps(error)
                if "checkform" in message.lower() or "invalid token" in message.lower():
                    self.login()
                    if attempt + 1 < retries:
                        params["api_token"] = self.check
                        continue
                raise DeezerError(f"{method}: {message[:300]}")
            return payload.get("results") or {}

        raise DeezerError(f"{method}: failed")
