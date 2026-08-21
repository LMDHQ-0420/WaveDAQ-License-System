from __future__ import annotations

import base64
import hashlib
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .local_storage import data_dir, read_json, write_json
from .local_crypto import decrypt_text, encrypt_text, machine_code_hash


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def load_or_create() -> dict[str, str]:
    path = data_dir() / "device.json"
    existing = read_json(path)
    if existing and existing.get("device_id") and existing.get("public_key") and existing.get("private_key_encrypted"):
        if existing.get("machine_code_hash") != machine_code_hash():
            raise RuntimeError("设备机器码不匹配，无法读取本机授权")
        try:
            stored_private = decrypt_text(str(existing["private_key_encrypted"]))
        except Exception as exc:
            raise RuntimeError("本地设备密钥损坏，请重新激活") from exc
        return {"device_id": str(existing["device_id"]), "private_key": stored_private, "public_key": str(existing["public_key"]), "machine_code_hash": machine_code_hash()}

    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes_raw()
    public_raw = private.public_key().public_bytes_raw()
    device_id = "dev_" + uuid.uuid4().hex
    value = {"device_id": device_id, "private_key": _b64(private_raw), "public_key": _b64(public_raw)}
    write_json(path, {"schema_version": 2, "device_id": device_id, "public_key": value["public_key"], "machine_code_hash": machine_code_hash(), "private_key_encrypted": encrypt_text(value["private_key"])})
    value["machine_code_hash"] = machine_code_hash()
    return value


def device_fingerprint() -> str:
    # 仅用于辅助显示和诊断；安全绑定使用公钥，不依赖硬件序列号。
    value = f"{uuid.getnode():x}"
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def private_key(identity: dict[str, str]) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(_unb64(identity["private_key"]))


def sign(identity: dict[str, str], message: str) -> str:
    return _b64(private_key(identity).sign(message.encode("utf-8")))
