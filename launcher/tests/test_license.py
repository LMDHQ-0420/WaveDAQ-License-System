from __future__ import annotations

import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.license_verifier import canonical_payload, verify_license


class LicenseTests(unittest.TestCase):
    def test_canonical_payload_excludes_signature(self) -> None:
        document = {"b": 2, "signature": "ignored", "a": {"z": 1, "y": 2}}
        self.assertEqual(canonical_payload(document), b'{"a":{"y":2,"z":1},"b":2}')


    def test_license_signature_and_device_binding(self) -> None:
        private = Ed25519PrivateKey.generate()
        public = private.public_key()
        import base64
        encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
        document = {
            "schema_version": "1",
            "license_id": "lic_test",
            "device_id": "dev_test",
            "device_public_key": encode(public.public_bytes_raw()),
            "issued_at": "2026-08-19T00:00:00Z",
            "expires_at": None,
            "offline_grace_days": 30,
            "products": [{"product_id": "wavedaq-8ch", "version_ranges": ["1.0.*"], "platforms": ["macos-arm64"]}],
        }
        signature = private.sign(canonical_payload(document))
        document["signature"] = encode(signature)
        identity = {"device_id": "dev_test", "public_key": document["device_public_key"], "private_key": encode(private.private_bytes_raw())}
        verify_license(document, identity, document["device_public_key"])
