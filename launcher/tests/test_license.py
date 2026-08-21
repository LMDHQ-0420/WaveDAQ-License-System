from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.license_verifier import canonical_payload, verify_expiry, verify_license
from src.local_crypto import machine_code_hash


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
            "products": [{"product_id": "wavedaq-8ch", "platforms": ["macos-arm64"]}],
        }
        signature = server_private.sign(canonical_payload(document))
        document["signature"] = encode(signature)
        identity = {"device_id": "dev_test", "public_key": document["device_public_key"], "machine_code_hash": machine_code_hash(), "private_key": encode(device_private.private_bytes_raw())}
        with tempfile.TemporaryDirectory() as directory, patch("src.license_verifier.data_dir", return_value=Path(directory)):
            verify_license(document, identity, encode(server_private.public_key().public_bytes_raw()))
        with tempfile.TemporaryDirectory() as directory, patch("src.license_verifier.data_dir", return_value=Path(directory)):
            (Path(directory) / "clock.dat").write_text("broken-clock", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "授权时钟数据损坏"):
                verify_license(document, identity, encode(server_private.public_key().public_bytes_raw()))

    def test_rejects_unrelated_device_private_key(self) -> None:
        device_private = Ed25519PrivateKey.generate()
        other_private = Ed25519PrivateKey.generate()
        import base64
        encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
        identity = {"device_id": "dev_test", "public_key": encode(device_private.public_key().public_bytes_raw()), "machine_code_hash": machine_code_hash(), "private_key": encode(other_private.private_bytes_raw())}
        from src.license_verifier import verify_device_binding
        with self.assertRaisesRegex(ValueError, "私钥与设备公钥不匹配"):
            verify_device_binding({"device_id": "dev_test", "device_public_key": identity["public_key"]}, identity)

    def test_offline_window_does_not_force_online_refresh(self) -> None:
        document = {"issued_at": "2020-01-01T00:00:00Z", "expires_at": None}
        verify_expiry(document)
