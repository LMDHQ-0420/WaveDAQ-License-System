#!/usr/bin/env python3
"""Generate a Worker ADMIN_PASSWORD_HASH without exposing the password."""

import base64
import getpass
import hashlib
import secrets


def encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


password = getpass.getpass("管理员密码: ")
if not password:
    raise SystemExit("密码不能为空")
if len(password) < 12:
    raise SystemExit("管理员密码至少需要 12 个字符")
if password != getpass.getpass("再次输入管理员密码: "):
    raise SystemExit("两次密码不一致")

# Cloudflare Workers Web Crypto currently caps PBKDF2 at 100,000 iterations.
iterations = 100_000
salt = secrets.token_bytes(16)
derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations, 32)
print(f"pbkdf2-sha256:{iterations}:{encode(salt)}:{encode(derived)}")
