from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any


def data_dir() -> Path:
    if platform.system() == "Windows":
        root = Path(os.environ.get("APPDATA", Path.home()))
    elif platform.system() == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = root / "WaveDAQ"
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    temporary.replace(path)


def save_license(document: dict[str, Any], make_active: bool = True) -> Path:
    license_id = str(document["license_id"])
    path = data_dir() / "licenses" / f"{license_id}.json"
    write_json(path, document)
    if make_active:
        write_json(data_dir() / "license.json", document)
    return path


def load_licenses() -> list[dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    directory = data_dir() / "licenses"
    if directory.exists():
        for path in directory.glob("*.json"):
            document = read_json(path)
            if document and document.get("license_id"):
                documents[str(document["license_id"])] = document
    legacy = read_json(data_dir() / "license.json")
    if legacy and legacy.get("license_id"):
        documents.setdefault(str(legacy["license_id"]), legacy)
        save_license(legacy, make_active=False)
    return list(documents.values())


def set_active_license(license_id: str) -> dict[str, Any]:
    document = read_json(data_dir() / "licenses" / f"{license_id}.json")
    if not document:
        raise RuntimeError("找不到该程序对应的本地授权")
    write_json(data_dir() / "license.json", document)
    return document


def save_catalog(license_id: str, catalog: dict[str, Any]) -> None:
    write_json(data_dir() / "catalogs" / f"{license_id}.json", catalog)


def load_catalogs() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    directory = data_dir() / "catalogs"
    if directory.exists():
        for path in directory.glob("*.json"):
            value = read_json(path)
            if value:
                result[path.stem] = value
    return result


def load_installations() -> list[dict[str, Any]]:
    value = read_json(data_dir() / "installations.json")
    return list(value.get("installations", [])) if value else []


def save_installation(record: dict[str, Any]) -> None:
    records = load_installations()
    records = [item for item in records if not (item.get("product_id") == record.get("product_id") and item.get("platform") == record.get("platform"))]
    records.append(record)
    write_json(data_dir() / "installations.json", {"installations": records})
