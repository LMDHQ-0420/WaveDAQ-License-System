from __future__ import annotations

import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.license_verifier import canonical_payload, verify_expiry, verify_license


class LicenseTests(unittest.TestCase):
    def test_canonical_payload_excludes_signature(self) -> None:
        document = {"b": 2, "signature": "ignored", "a": {"z": 1, "y": 2}}
        self.assertEqual(canonical_payload(document), b'{"a":{"y":2,"z":1},"b":2}')


    def test_license_signature_and_device_binding(self) -> None:
        server_private = Ed25519PrivateKey.generate()
        device_private = Ed25519PrivateKey.generate()
        import base64
        encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
        document = {
            "schema_version": "1",
            "license_id": "lic_test",
            "device_id": "dev_test",
            "device_public_key": encode(device_private.public_key().public_bytes_raw()),
            "issued_at": "2026-08-19T00:00:00Z",
            "expires_at": None,
            "offline_grace_days": 30,
            "products": [{"product_id": "wavedaq-8ch", "version_ranges": ["1.0.*"], "platforms": ["macos-arm64"]}],
        }
        signature = server_private.sign(canonical_payload(document))
        document["signature"] = encode(signature)
        identity = {"device_id": "dev_test", "public_key": document["device_public_key"], "private_key": encode(device_private.private_bytes_raw())}
        with patch("src.license_verifier.keyring.get_password", return_value=None), patch("src.license_verifier.keyring.set_password"):
            verify_license(document, identity, encode(server_private.public_key().public_bytes_raw()))

    def test_rejects_unrelated_device_private_key(self) -> None:
        device_private = Ed25519PrivateKey.generate()
        other_private = Ed25519PrivateKey.generate()
        import base64
        encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
        identity = {"device_id": "dev_test", "public_key": encode(device_private.public_key().public_bytes_raw()), "private_key": encode(other_private.private_bytes_raw())}
        from src.license_verifier import verify_device_binding
        with self.assertRaisesRegex(ValueError, "私钥与设备公钥不匹配"):
            verify_device_binding({"device_id": "dev_test", "device_public_key": identity["public_key"]}, identity)

    def test_rejects_expired_offline_window(self) -> None:
        document = {"issued_at": "2020-01-01T00:00:00Z", "expires_at": None, "offline_grace_days": 30}
        with self.assertRaisesRegex(ValueError, "离线授权宽限期已结束"):
            verify_expiry(document)
