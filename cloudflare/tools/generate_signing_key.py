#!/usr/bin/env python3
"""Generate an Ed25519 JWK for the Cloudflare Worker and a public key for clients."""

import base64
import json
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def main() -> int:
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes_raw()
    public = key.public_key().public_bytes_raw()
    print("保存以下 JSON 作为 Cloudflare Secret LICENSE_SIGNING_PRIVATE_KEY：", file=sys.stderr)
    print(json.dumps({"kty": "OKP", "crv": "Ed25519", "x": b64(public), "d": b64(private)}, separators=(",", ":")))
    print("\n将以下值内置到 Launcher 和 WaveDAQ：", file=sys.stderr)
    print(b64(public), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
