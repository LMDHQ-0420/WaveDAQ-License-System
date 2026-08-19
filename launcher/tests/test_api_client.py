from __future__ import annotations

import base64
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.api_client import LicenseApi


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


if __name__ == "__main__":
    unittest.main()
