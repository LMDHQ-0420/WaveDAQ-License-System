from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any

from .local_crypto import decrypt_text, encrypt_text


def data_dir() -> Path:
    if platform.system() == "Windows":
        root = Path(os.environ.get("APPDATA", Path.home()))
    elif platform.system() == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = root / "WaveDAQ-Launcher"
    legacy_path = root / "WaveDAQ"
    if not path.exists() and legacy_path.exists():
        try:
            legacy_path.replace(path)
        except OSError:
            # A read-only or concurrently used legacy directory is still
            # readable by callers; new data will use the new path when possible.
            pass
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    temporary.replace(path)


def read_protected_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(decrypt_text(path.read_text(encoding="utf-8")))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def write_protected_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    encrypted = encrypt_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    temporary.write_text(encrypted, encoding="utf-8")
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    temporary.replace(path)


def save_license(document: dict[str, Any], make_active: bool = True) -> Path:
    license_id = str(document["license_id"])
    revoked = load_revoked_license_ids()
    if license_id in revoked:
        revoked.remove(license_id)
        write_protected_json(data_dir() / "revoked_licenses.json", {"license_ids": sorted(revoked)})
    path = data_dir() / "licenses" / f"{license_id}.json"
    write_protected_json(path, document)
    if make_active:
        write_protected_json(data_dir() / "license.json", document)
    return path


def load_licenses() -> list[dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    revoked = load_revoked_license_ids()
    directory = data_dir() / "licenses"
    if directory.exists():
        for path in directory.glob("*.json"):
            document = read_protected_json(path) or read_json(path)
            if document and document.get("license_id") and str(document["license_id"]) not in revoked:
                documents[str(document["license_id"])] = document
    legacy = read_protected_json(data_dir() / "license.json") or read_json(data_dir() / "license.json")
    if legacy and legacy.get("license_id") and str(legacy["license_id"]) not in revoked:
        documents.setdefault(str(legacy["license_id"]), legacy)
        save_license(legacy, make_active=False)
    return list(documents.values())


def set_active_license(license_id: str) -> dict[str, Any]:
    if license_id in load_revoked_license_ids():
        raise RuntimeError("该授权已被服务器撤销或解绑")
    path = data_dir() / "licenses" / f"{license_id}.json"
    document = read_protected_json(path) or read_json(path)
    if not document:
        raise RuntimeError("找不到该程序对应的本地授权")
    write_protected_json(data_dir() / "license.json", document)
    return document


def load_revoked_license_ids() -> set[str]:
    value = read_protected_json(data_dir() / "revoked_licenses.json") or read_json(data_dir() / "revoked_licenses.json")
    return {str(item) for item in value.get("license_ids", [])} if value else set()


def mark_license_revoked(license_id: str) -> None:
    revoked = load_revoked_license_ids()
    revoked.add(license_id)
    write_protected_json(data_dir() / "revoked_licenses.json", {"license_ids": sorted(revoked)})
    for path in (data_dir() / "licenses" / f"{license_id}.json", data_dir() / "catalogs" / f"{license_id}.json"):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    active_path = data_dir() / "license.json"
    active = read_protected_json(active_path) or read_json(active_path)
    if active and str(active.get("license_id")) == license_id:
        try:
            active_path.unlink()
        except FileNotFoundError:
            pass


def save_catalog(license_id: str, catalog: dict[str, Any]) -> None:
    write_protected_json(data_dir() / "catalogs" / f"{license_id}.json", catalog)


def load_catalogs() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    directory = data_dir() / "catalogs"
    if directory.exists():
        for path in directory.glob("*.json"):
            value = read_protected_json(path) or read_json(path)
            if value:
                result[path.stem] = value
    return result


def load_installations() -> list[dict[str, Any]]:
    value = read_protected_json(data_dir() / "installations.json") or read_json(data_dir() / "installations.json")
    return list(value.get("installations", [])) if value else []


def save_installation(record: dict[str, Any]) -> None:
    records = load_installations()
    records = [item for item in records if not (item.get("product_id") == record.get("product_id") and item.get("platform") == record.get("platform"))]
    records.append(record)
    write_protected_json(data_dir() / "installations.json", {"installations": records})
