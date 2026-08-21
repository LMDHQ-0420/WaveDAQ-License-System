from __future__ import annotations

import base64
import io
import unittest
from urllib.error import HTTPError
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.api_client import LicenseApi, LicenseApiError


def encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class SignedRequestTests(unittest.TestCase):
    def test_device_headers_sign_request_and_nonce(self) -> None:
        private = Ed25519PrivateKey.generate()
        identity = {"device_id": "dev_" + "a" * 32, "public_key": encode(private.public_key().public_bytes_raw()), "private_key": encode(private.private_bytes_raw())}
        headers = LicenseApi("https://example.test")._device_headers("GET", "/api/releases", "lic_test", identity)
        self.assertRegex(headers["x-device-nonce"], r"^[a-f0-9]{32}$")
        message = f"GET\n/api/releases\nlic_test\n{identity['device_id']}\n{headers['x-device-timestamp']}\n{headers['x-device-nonce']}"
        private.public_key().verify(decode(headers["x-device-signature"]), message.encode())

    def test_signed_request_preserves_http_status_and_server_message(self) -> None:
        private = Ed25519PrivateKey.generate()
        identity = {"device_id": "dev_" + "b" * 32, "public_key": encode(private.public_key().public_bytes_raw()), "private_key": encode(private.private_bytes_raw())}
        response = HTTPError("https://example.test", 403, "Forbidden", {}, io.BytesIO(b'{"error":"license revoked"}'))
        with patch("src.api_client.urlopen", side_effect=response):
            with self.assertRaises(LicenseApiError) as result:
                LicenseApi("https://example.test").refresh("lic_test", identity)
        self.assertEqual(result.exception.status, 403)
        self.assertEqual(str(result.exception), "license revoked")

    def test_requests_use_launcher_user_agent(self) -> None:
        private = Ed25519PrivateKey.generate()
        identity = {"device_id": "dev_" + "c" * 32, "public_key": encode(private.public_key().public_bytes_raw()), "private_key": encode(private.private_bytes_raw())}
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"ok":true}'
        with patch("src.api_client.urlopen", return_value=response) as opened:
            LicenseApi("https://example.test").refresh("lic_test", identity)
        request = opened.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "WaveDAQ-Launcher/1.0")


if __name__ == "__main__":
    unittest.main()
