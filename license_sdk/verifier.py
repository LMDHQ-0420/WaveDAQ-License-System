from __future__ import annotations

import base64
import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .config import PRODUCT_ID, SERVER_PUBLIC_KEY
from .local_crypto import decrypt_text, encrypt_text, machine_code_hash

DATA_DIRECTORY_NAME = "WaveDAQ-Launcher"


class LicenseError(RuntimeError):
    """Raised when the local license cannot authorize the product."""


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sorted(value: Any) -> Any:
    if isinstance(value, list):
        return [_sorted(item) for item in value]
    if isinstance(value, dict):
        return {key: _sorted(value[key]) for key in sorted(value)}
    return value


def canonical_payload(document: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in document.items() if key != "signature"}
    return json.dumps(_sorted(unsigned), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


_payload = canonical_payload


def data_dir() -> Path:
    if platform.system() == "Windows":
        root = Path(os.environ.get("APPDATA", Path.home()))
    elif platform.system() == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / DATA_DIRECTORY_NAME


def _platform_id() -> str:
    if platform.system() == "Darwin":
        return "macos-arm64" if "arm" in platform.machine().lower() else "macos-x64"
    if platform.system() == "Windows":
        return "windows-x64"
    return "linux-x64"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        try:
            value = json.loads(raw)
        except ValueError:
            value = json.loads(decrypt_text(raw.strip()))
    except (OSError, ValueError) as exc:
        raise LicenseError("未找到有效的本机授权，请先运行 WaveDAQ-Launcher 激活") from exc
    if not isinstance(value, dict):
        raise LicenseError("本机授权文件格式无效")
    return value


def verify_signature(document: dict[str, Any], server_public_key: str) -> None:
    signature = document.get("signature")
    if not isinstance(signature, str):
        raise LicenseError("授权文件缺少签名")
    try:
        Ed25519PublicKey.from_public_bytes(_b64decode(server_public_key)).verify(
            _b64decode(signature), canonical_payload(document)
        )
    except Exception as exc:
        raise LicenseError("授权签名验证失败") from exc


def verify_device_binding(document: dict[str, Any], identity: dict[str, str]) -> None:
    if document.get("device_id") != identity.get("device_id"):
        raise LicenseError("授权文件不是本设备的授权")
    if document.get("device_public_key") != identity.get("public_key"):
        raise LicenseError("设备公钥不匹配")
    if identity.get("machine_code_hash") != machine_code_hash():
        raise LicenseError("设备机器码不匹配")
    try:
        private = Ed25519PrivateKey.from_private_bytes(_b64decode(decrypt_text(str(identity["private_key_encrypted"]))))
        derived_public = base64.urlsafe_b64encode(private.public_key().public_bytes_raw()).decode("ascii").rstrip("=")
        if derived_public != identity.get("public_key"):
            raise ValueError("设备私钥与公钥不匹配")
        challenge = b"wavedaq-local-license-check"
        private.public_key().verify(private.sign(challenge), challenge)
    except Exception as exc:
        raise LicenseError("授权签名或设备私钥验证失败") from exc


def verify_expiry(document: dict[str, Any]) -> None:
    expires_at = document.get("expires_at")
    if expires_at:
        try:
            expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except ValueError as exc:
            raise LicenseError("授权过期时间格式无效") from exc
        if datetime.now(timezone.utc) >= expiry:
            raise LicenseError("授权已过期")


def allows(document: dict[str, Any], product_id: str, platform_id: str) -> bool:
    for product in document.get("products", []):
        if product.get("product_id") != product_id or platform_id not in product.get("platforms", []):
            continue
        return True
    return False


def verify_license(document: dict[str, Any], identity: dict[str, str], server_public_key: str) -> None:
    verify_signature(document, server_public_key)
    verify_device_binding(document, identity)
    verify_expiry(document)
    now = time.time()
    clock_path = data_dir() / "clock.dat"
    last_value = None
    if clock_path.exists():
        try:
            last_value = decrypt_text(clock_path.read_text(encoding="utf-8").strip())
        except Exception as exc:
            raise LicenseError("本地授权时钟数据损坏，请重新激活") from exc
    try:
        last_timestamp = float(last_value) if last_value else 0.0
    except (TypeError, ValueError) as exc:
        raise LicenseError("本地授权时钟数据损坏，请重新激活") from exc
    if now + 300 < last_timestamp:
        raise LicenseError("检测到系统时间回拨，无法验证离线授权")
    clock_path.write_text(encrypt_text(str(max(now, last_timestamp))), encoding="utf-8")
    try:
        clock_path.chmod(0o600)
    except OSError:
        pass
    if not allows(document, PRODUCT_ID, _platform_id()):
        raise LicenseError("当前设备未获得此产品或平台的授权")


def require_valid_license() -> None:
    if SERVER_PUBLIC_KEY.startswith("REPLACE_") or PRODUCT_ID.startswith("REPLACE_"):
        raise LicenseError("软件尚未配置正式授权参数")
    directory = data_dir()
    identity = _read_json(directory / "device.json")
    document = _read_json(directory / "license.json")
    verify_license(document, identity, SERVER_PUBLIC_KEY)
