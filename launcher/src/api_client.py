from __future__ import annotations

import json
import ssl
import time
import uuid
from pathlib import Path
from collections.abc import Callable
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any

try:
    import certifi
except ImportError:  # Development environments may not have optional CA data installed yet.
    certifi = None

from src.device_identity import sign
from src.release_downloader import download_verified


class LicenseApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


NETWORK_RETRY_MESSAGE = "网络波动，请重试"


class LicenseApi:
    def __init__(self, base_url: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.ssl_context = ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(self.base_url + path, data=data, method=method, headers={"content-type": "application/json", "accept": "application/json", "user-agent": "WaveDAQ-Launcher/1.0"})
        try:
            with urlopen(request, timeout=self.timeout, context=self.ssl_context) as response:
                return json.loads(response.read().decode())
        except (HTTPError, URLError) as exc:
            if isinstance(exc, HTTPError):
                try:
                    detail = json.loads(exc.read().decode()).get("error", str(exc))
                except Exception:
                    detail = str(exc)
            else:
                detail = NETWORK_RETRY_MESSAGE
            raise LicenseApiError(detail, exc.code if isinstance(exc, HTTPError) else None) from exc

    def activate(self, code: str, device_id: str, public_key: str, fingerprint: str) -> dict[str, Any]:
        return self._request("POST", "/api/activate", {"activation_code": code, "device_id": device_id, "device_public_key": public_key, "fingerprint": fingerprint})

    def _device_headers(self, method: str, path: str, license_id: str, identity: dict[str, str]) -> dict[str, str]:
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex
        message = f"{method}\n{path}\n{license_id}\n{identity['device_id']}\n{timestamp}\n{nonce}"
        return {"x-device-id": identity["device_id"], "x-device-timestamp": timestamp, "x-device-nonce": nonce, "x-device-signature": sign(identity, message)}

    def _signed_request(self, method: str, path: str, license_id: str, identity: dict[str, str]) -> dict[str, Any]:
        query_path = f"{path}?{urlencode({'license_id': license_id})}"
        request = Request(self.base_url + query_path, method=method, headers={"accept": "application/json", "user-agent": "WaveDAQ-Launcher/1.0", **self._device_headers(method, path, license_id, identity)})
        try:
            with urlopen(request, timeout=self.timeout, context=self.ssl_context) as response:
                return json.loads(response.read().decode())
        except (HTTPError, URLError) as exc:
            detail = NETWORK_RETRY_MESSAGE
            if isinstance(exc, HTTPError):
                try:
                    detail = json.loads(exc.read().decode()).get("error", detail)
                except Exception:
                    pass
            raise LicenseApiError(detail, exc.code if isinstance(exc, HTTPError) else None) from exc

    def releases(self, license_id: str, identity: dict[str, str]) -> dict[str, Any]:
        return self._signed_request("GET", "/api/releases", license_id, identity)

    def refresh(self, license_id: str, identity: dict[str, str]) -> dict[str, Any]:
        return self._signed_request("POST", "/api/license/refresh", license_id, identity)

    def download(self, download_path: str, license_id: str, identity: dict[str, str], expected_sha256: str, destination: Path, progress: Callable[[int, int], None] | None = None) -> Path:
        path = download_path.split("?", 1)[0]
        headers = {"user-agent": "WaveDAQ-Launcher/1.0", **self._device_headers("GET", path, license_id, identity)}
        return download_verified(self.base_url + download_path, expected_sha256, destination, headers, progress)
