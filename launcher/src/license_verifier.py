from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .local_crypto import decrypt_text, encrypt_text, machine_code_hash
from .local_storage import data_dir


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sorted(value: Any) -> Any:
    if isinstance(value, list):
        return [_sorted(item) for item in value]
    if isinstance(value, dict):
        return {key: _sorted(value[key]) for key in sorted(value)}
    return value


def canonical_payload(license_document: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in license_document.items() if key != "signature"}
    return json.dumps(_sorted(unsigned), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def verify_signature(license_document: dict[str, Any], server_public_key: str) -> None:
    signature = license_document.get("signature")
    if not isinstance(signature, str):
        raise ValueError("授权文件缺少签名")
    Ed25519PublicKey.from_public_bytes(_unb64(server_public_key)).verify(_unb64(signature), canonical_payload(license_document))


def verify_device_binding(license_document: dict[str, Any], identity: dict[str, str]) -> None:
    if license_document.get("device_id") != identity["device_id"]:
        raise ValueError("授权文件不是本设备的授权")
    if license_document.get("device_public_key") != identity["public_key"]:
        raise ValueError("设备公钥不匹配")
    if identity.get("machine_code_hash") != machine_code_hash():
        raise ValueError("设备机器码不匹配")
    challenge = b"wavedaq-local-license-check"
    from src.device_identity import private_key
    private = private_key(identity)
    derived_public = base64.urlsafe_b64encode(private.public_key().public_bytes_raw()).decode("ascii").rstrip("=")
    if derived_public != identity["public_key"]:
        raise ValueError("本地设备私钥与设备公钥不匹配")
    private.public_key().verify(private.sign(challenge), challenge)


def verify_expiry(license_document: dict[str, Any]) -> None:
    expires_at = license_document.get("expires_at")
    if expires_at:
        expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if datetime.now(timezone.utc) >= expiry:
            raise ValueError("授权已过期")

def verify_license(license_document: dict[str, Any], identity: dict[str, str], server_public_key: str) -> None:
    verify_signature(license_document, server_public_key)
    verify_device_binding(license_document, identity)
    verify_expiry(license_document)
    now = time.time()
    clock_path = data_dir() / "clock.dat"
    last_value = None
    if clock_path.exists():
        try:
            last_value = decrypt_text(clock_path.read_text(encoding="utf-8").strip())
        except Exception as exc:
            raise ValueError("本地授权时钟数据损坏，请重新激活") from exc
    try:
        last_timestamp = float(last_value) if last_value else 0.0
    except (TypeError, ValueError) as exc:
        raise ValueError("本地授权时钟数据损坏，请重新激活") from exc
    if now + 300 < last_timestamp:
        raise ValueError("检测到系统时间回拨，无法验证离线授权")
    clock_path.write_text(encrypt_text(str(max(now, last_timestamp))), encoding="utf-8")
    try:
        clock_path.chmod(0o600)
    except OSError:
        pass
