from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from src.api_client import LicenseApi
from src.config import API_URL, SERVER_PUBLIC_KEY
from src.device_identity import device_fingerprint, load_or_create
from src.license_verifier import verify_license
from src.local_storage import data_dir, read_json, write_json
from src.software_installer import launch

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
    response = LicenseApi(API_URL).activate(args.code, identity["device_id"], identity["public_key"], device_fingerprint())
    license_document = response["license"]
    verify_license(license_document, identity, SERVER_PUBLIC_KEY)
    write_json(license_path(), license_document)
    print(f"激活成功，授权已保存到 {license_path()}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    identity = load_or_create()
    document = read_json(license_path())
    if not document:
        print("未找到本地授权文件", file=sys.stderr)
        return 2
    verify_license(document, identity, SERVER_PUBLIC_KEY)
    print("本地授权验证成功")
    return 0


def cmd_releases(args: argparse.Namespace) -> int:
    identity = load_or_create()
    document = read_json(license_path())
    if not document:
        raise RuntimeError("请先激活设备")
    verify_license(document, identity, SERVER_PUBLIC_KEY)
    response = LicenseApi(API_URL).releases(document["license_id"], identity)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0


def cmd_refresh(_: argparse.Namespace) -> int:
    identity = load_or_create()
    document = read_json(license_path())
    if not document:
        raise RuntimeError("请先激活设备")
    response = LicenseApi(API_URL).refresh(document["license_id"], identity)
    refreshed = response["license"]
    verify_license(refreshed, identity, SERVER_PUBLIC_KEY)
    write_json(license_path(), refreshed)
    print("授权已刷新")
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    identity = load_or_create()
    document = read_json(license_path())
    if not document:
        raise RuntimeError("请先激活设备")
    verify_license(document, identity, SERVER_PUBLIC_KEY)
    api = LicenseApi(API_URL)
    releases = api.releases(document["license_id"], identity).get("releases", [])
    release = next((item for item in releases if item.get("id") == args.release_id), None)
    if not release:
        raise RuntimeError("该版本不存在或不在授权范围内")
    path = api.download(release["download_url"], document["license_id"], identity, release["sha256"], Path(args.output))
    print(f"下载和校验完成：{path}")
    return 0


def cmd_launch(args: argparse.Namespace) -> int:
    identity = load_or_create()
    document = read_json(license_path())
    if not document:
        raise RuntimeError("请先激活设备")
    verify_license(document, identity, SERVER_PUBLIC_KEY)
    launch(Path(args.path), args.arguments)
    print("软件已启动")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="WaveDAQ License Launcher")
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("device", help="显示本机设备身份").set_defaults(func=cmd_device)
    activate = sub.add_parser("activate", help="使用一次性激活码激活")
    activate.add_argument("code")
    activate.set_defaults(func=cmd_activate)
    sub.add_parser("verify", help="离线验证本地授权").set_defaults(func=cmd_verify)
    sub.add_parser("releases", help="查询授权允许的版本").set_defaults(func=cmd_releases)
    sub.add_parser("refresh", help="联网刷新离线授权").set_defaults(func=cmd_refresh)
    download = sub.add_parser("download", help="下载并校验授权版本")
    download.add_argument("release_id")
    download.add_argument("output")
    download.set_defaults(func=cmd_download)
    launch_parser = sub.add_parser("launch", help="验证授权后启动已安装软件")
    launch_parser.add_argument("path")
    launch_parser.add_argument("arguments", nargs=argparse.REMAINDER)
    launch_parser.set_defaults(func=cmd_launch)
    return result


if __name__ == "__main__":
    try:
        arguments = parser().parse_args()
        raise SystemExit(arguments.func(arguments))
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1)
