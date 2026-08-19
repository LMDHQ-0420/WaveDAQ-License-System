from __future__ import annotations

import base64
import hashlib
import uuid

import keyring
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .local_storage import data_dir, read_json, write_json

KEYRING_SERVICE = "WaveDAQ License Device Key"


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def load_or_create() -> dict[str, str]:
    path = data_dir() / "device.json"
    existing = read_json(path)
    if existing and existing.get("device_id") and existing.get("public_key"):
        device_id = str(existing["device_id"])
        stored_private = keyring.get_password(KEYRING_SERVICE, device_id)
        legacy_private = existing.get("private_key")
        if not stored_private and legacy_private:
            stored_private = str(legacy_private)
            keyring.set_password(KEYRING_SERVICE, device_id, stored_private)
            write_json(path, {"device_id": device_id, "public_key": str(existing["public_key"])})
        if not stored_private:
            raise RuntimeError("系统安全存储中找不到设备私钥，请由管理员解绑后重新激活")
        return {"device_id": device_id, "private_key": stored_private, "public_key": str(existing["public_key"])}

    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes_raw()
    public_raw = private.public_key().public_bytes_raw()
    device_id = "dev_" + uuid.uuid4().hex
    value = {"device_id": device_id, "private_key": _b64(private_raw), "public_key": _b64(public_raw)}
    keyring.set_password(KEYRING_SERVICE, device_id, value["private_key"])
    write_json(path, {"device_id": device_id, "public_key": value["public_key"]})
    return value


def device_fingerprint() -> str:
    # 仅用于辅助显示和诊断；安全绑定使用公钥，不依赖硬件序列号。
    value = f"{uuid.getnode():x}"
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def private_key(identity: dict[str, str]) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(_unb64(identity["private_key"]))


def sign(identity: dict[str, str], message: str) -> str:
    return _b64(private_key(identity).sign(message.encode("utf-8")))
