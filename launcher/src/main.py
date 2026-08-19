from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path

from src.api_client import LicenseApi
from src.device_identity import device_fingerprint, load_or_create
from src.license_verifier import verify_license
from src.local_storage import data_dir, read_json, write_json

DEFAULT_API_URL = os.environ.get("WAVEDAQ_LICENSE_API", "https://wavedaq-license.example.workers.dev")
# 部署 Worker 后，将此值替换为服务器签发公钥；它不是服务器私钥。
SERVER_PUBLIC_KEY = os.environ.get("WAVEDAQ_LICENSE_PUBLIC_KEY", "REPLACE_WITH_SERVER_ED25519_PUBLIC_KEY")


def current_platform() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        return "macos-arm64" if "arm" in machine else "macos-x64"
    if system == "windows":
        return "windows-x64"
    return "linux-x64"


def license_path() -> Path:
    return data_dir() / "license.json"


def cmd_device(_: argparse.Namespace) -> int:
    identity = load_or_create()
    print(json.dumps({"device_id": identity["device_id"], "device_public_key": identity["public_key"], "fingerprint": device_fingerprint()}, indent=2))
    return 0


def cmd_activate(args: argparse.Namespace) -> int:
    identity = load_or_create()
    response = LicenseApi(args.api).activate(args.code, identity["device_id"], identity["public_key"], device_fingerprint())
    license_document = response["license"]
    verify_license(license_document, identity, args.server_public_key)
    write_json(license_path(), license_document)
    print(f"激活成功，授权已保存到 {license_path()}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    identity = load_or_create()
    document = read_json(license_path())
    if not document:
        print("未找到本地授权文件", file=sys.stderr)
        return 2
    verify_license(document, identity, args.server_public_key)
    print("本地授权验证成功")
    return 0


def cmd_releases(args: argparse.Namespace) -> int:
    identity = load_or_create()
    document = read_json(license_path())
    if not document:
        raise RuntimeError("请先激活设备")
    verify_license(document, identity, args.server_public_key)
    response = LicenseApi(args.api).releases(document["license_id"], identity["device_id"])
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="WaveDAQ License Launcher")
    result.add_argument("--api", default=DEFAULT_API_URL)
    result.add_argument("--server-public-key", default=SERVER_PUBLIC_KEY)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("device", help="显示本机设备身份").set_defaults(func=cmd_device)
    activate = sub.add_parser("activate", help="使用一次性激活码激活")
    activate.add_argument("code")
    activate.set_defaults(func=cmd_activate)
    sub.add_parser("verify", help="离线验证本地授权").set_defaults(func=cmd_verify)
    sub.add_parser("releases", help="查询授权允许的版本").set_defaults(func=cmd_releases)
    return result


if __name__ == "__main__":
    try:
        arguments = parser().parse_args()
        raise SystemExit(arguments.func(arguments))
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1)
