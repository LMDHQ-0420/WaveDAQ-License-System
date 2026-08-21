from __future__ import annotations

import base64
import hashlib
import os
import platform
import uuid

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


_SALT = b"WaveDAQ-Launcher-local-storage-v1"


def machine_code() -> str:
    return f"{platform.system()}|{platform.machine()}|{uuid.getnode():x}"


def machine_code_hash() -> str:
    return hashlib.sha256(machine_code().encode("utf-8")).hexdigest()


def _key() -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=_SALT, info=b"device-storage").derive(machine_code().encode("utf-8"))


def encrypt_text(value: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, value.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii").rstrip("=")


def decrypt_text(value: str) -> str:
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if len(raw) < 13:
        raise ValueError("本地加密数据格式无效")
    return AESGCM(_key()).decrypt(raw[:12], raw[12:], None).decode("utf-8")
