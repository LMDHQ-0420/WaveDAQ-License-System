from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import keyring

CLOCK_SERVICE = "WaveDAQ License Clock"


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
    challenge = b"wavedaq-local-license-check"
    from src.device_identity import private_key
    private = private_key(identity)
    derived_public = base64.urlsafe_b64encode(private.public_key().public_bytes_raw()).decode("ascii").rstrip("=")
    if derived_public != identity["public_key"]:
        raise ValueError("系统安全存储中的私钥与设备公钥不匹配")
    private.public_key().verify(private.sign(challenge), challenge)


def verify_expiry(license_document: dict[str, Any]) -> None:
    expires_at = license_document.get("expires_at")
    if expires_at:
        expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if datetime.now(timezone.utc) >= expiry:
            raise ValueError("授权已过期")

    # offline_grace_days is retained for schema compatibility, but it is not an
    # online heartbeat. Once activated, the signed license is valid offline
    # until expires_at (or indefinitely when expires_at is null).


def verify_license(license_document: dict[str, Any], identity: dict[str, str], server_public_key: str) -> None:
    verify_signature(license_document, server_public_key)
    verify_device_binding(license_document, identity)
    verify_expiry(license_document)
    now = time.time()
    last_value = keyring.get_password(CLOCK_SERVICE, identity["device_id"])
    try:
        last_timestamp = float(last_value) if last_value else 0.0
    except (TypeError, ValueError) as exc:
        raise ValueError("系统安全存储中的授权时钟数据损坏，请重新激活") from exc
    if now + 300 < last_timestamp:
        raise ValueError("检测到系统时间回拨，无法验证离线授权")
    keyring.set_password(CLOCK_SERVICE, identity["device_id"], str(max(now, last_timestamp)))


def allows(license_document: dict[str, Any], product_id: str, version: str, platform: str) -> bool:
    for product in license_document.get("products", []):
        if product.get("product_id") != product_id or platform not in product.get("platforms", []):
            continue
        for version_range in product.get("version_ranges", []):
            if version_range == "*" or version_range == version or (version_range.endswith(".*") and version.startswith(version_range[:-1])):
                return True
    return False
