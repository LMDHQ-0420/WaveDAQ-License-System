from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any


class LicenseApiError(RuntimeError):
    pass


class LicenseApi:
    def __init__(self, base_url: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(self.base_url + path, data=data, method=method, headers={"content-type": "application/json", "accept": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except (HTTPError, URLError) as exc:
            if isinstance(exc, HTTPError):
                try:
                    detail = json.loads(exc.read().decode()).get("error", str(exc))
                except Exception:
                    detail = str(exc)
            else:
                detail = str(exc)
            raise LicenseApiError(detail) from exc

    def activate(self, code: str, device_id: str, public_key: str, fingerprint: str) -> dict[str, Any]:
        return self._request("POST", "/api/activate", {"activation_code": code, "device_id": device_id, "device_public_key": public_key, "fingerprint": fingerprint})

    def releases(self, license_id: str, device_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/releases?license_id={license_id}&device_id={device_id}")
