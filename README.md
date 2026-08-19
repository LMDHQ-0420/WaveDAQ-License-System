# WaveDAQ License System

WaveDAQ 的启动器、离线授权验证、Cloudflare 授权服务和管理后台。

## 项目结构

```text
launcher/             本地启动器和安装器
cloudflare/worker/    Cloudflare Worker API 与 D1 数据库
cloudflare/admin/     Cloudflare 管理后台前端
shared/               启动器与服务端共享的数据协议
```

## 核心流程

```text
Launcher → Cloudflare /api/activate → D1
                                      ↓
Launcher ← 服务器签名授权文件 ←───────┘
    ↓
离线验证设备私钥、授权签名、型号、版本和有效期
```

真实 WaveDAQ 运行时必须再次执行本地授权验证，不能只依赖 Launcher。

## 开发顺序

```bash
# 启动器依赖
cd launcher
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m src.main device

# Cloudflare 项目
cd ../cloudflare
npm run install:all
npm run build:admin
```

生产部署前，需要创建 D1 数据库、应用迁移，并配置 `LICENSE_SIGNING_PRIVATE_KEY` 和 `ADMIN_TOKEN` Secret。

## 安全说明

服务器签名私钥、Cloudflare API Token、GitHub Token、真实激活码和客户数据不得提交到 Git。
