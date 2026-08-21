<p align="center">
  <img src="logo.png" width="120" alt="License System Logo"/>
</p>

<h1 align="center">WaveDAQ License System</h1>
<p align="center">面向多个桌面软件的授权、分发与离线校验系统</p>
<p align="center"><strong>中文</strong> | <a href="README-EN.md">English</a></p>
<p align="center"><a href="https://github.com/LMDHQ-0420/WaveDAQ-License-System/releases">下载</a> · <a href="#技术报告">技术报告</a></p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11"/>
  <img src="https://img.shields.io/badge/PySide6-Qt-41CD52?logo=qt" alt="PySide6"/>
  <img src="https://img.shields.io/badge/Cloudflare-Workers-F38020?logo=cloudflare&logoColor=white" alt="Cloudflare Workers"/>
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey" alt="Platforms"/>
</p>

## 支持的软件

| 图示 | 软件 | 说明 |
|---|---|---|
| <img src="assets/WaveDAG.png" width="180" alt="WaveDAQ 界面"/> | **WaveDAQ** | WaveDAQ 是一个面向实验数据采集的桌面软件，支持 8 通道 UDP 实时数据接收、波形显示和数据处理。 |

## 用户使用

### 一、获取验证软件

验证系统发行包位于 [GitHub Releases](https://github.com/LMDHQ-0420/WaveDAQ-License-System/releases)。macOS 下载对应的 DMG，Windows 下载带有 `-setup.exe` 后缀的安装程序。

### 二、获取激活码

激活码由管理员创建和分发。如需申请激活码、查询授权产品或处理设备绑定，请联系：

**sunyuxiang25@mails.ucas.edu.cn**

### 三、激活和使用

1. 启动 WaveDAQ-Launcher。
2. 输入激活码，提交设备授权申请。
3. 激活成功后，Launcher 显示当前授权的产品。
4. 选择产品并执行安装或启动。
5. Launcher 按电脑平台匹配产品 GitHub Release 安装包，并校验 SHA-256。
6. 安装完成后，从 Launcher 打开已安装产品。

首次激活需要联网。激活成功后，授权文件保存在本机，产品可以按授权规则离线启动；再次联网时，Launcher 可以同步授权状态和产品信息。

一个激活码只能绑定一个设备。更换电脑前，需要联系管理员解除原设备绑定。授权期限支持永久授权和自定义过期时间。

### 四、从源码安装

需要 Python 3.11、Conda 和网络连接：

```
git clone https://github.com/LMDHQ-0420/WaveDAQ-License-System.git
cd WaveDAQ-License-System
conda create -n WaveDAQLaucher python=3.11 -y
conda activate WaveDAQLaucher
pip install -r launcher/requirements.txt
python launcher/src/main.py
```

源码运行使用 launcher/src/config.py 中配置的 Worker 地址和服务器公钥，适合开发和测试。普通用户使用 Releases 中的图形程序。

### 五、常见问题

#### 1. 激活码从哪里获得？

联系 sunyuxiang25@mails.ucas.edu.cn，说明需要使用的产品和操作系统。

#### 2. 为什么激活时需要联网？

服务器需要确认激活码、授权产品、有效期和设备绑定关系，并签发本机授权。首次激活后，不要求每次启动联网。

#### 3. 一个激活码能在两台电脑上使用吗？

不能。一个激活码只允许绑定一个设备。更换电脑需要联系管理员解绑。

#### 4. 离线时可以使用吗？

可以。完成首次激活后，Launcher 和产品使用本地签名授权校验。自定义期限授权会在本地按过期时间失效。

#### 5. 为什么看不到某个产品？

产品必须由管理员登记，且当前激活码必须包含该产品授权。

#### 6. Launcher 和产品分别是什么？

Launcher 是统一的授权、安装和启动入口；产品是实际提供业务功能的桌面软件。一个 Launcher 可以管理多个产品。

#### 7. 如何反馈问题？

请将操作系统、Launcher 提示、产品名称和复现步骤发送至 sunyuxiang25@mails.ucas.edu.cn。不要提交设备私钥、管理员密码或 GitHub Token。

## 技术报告

### 一、数据流

```
数据流/
├── 管理员后台
│   ├── 产品名称、产品 ID、GitHub 仓库
│   │   └── 写入 → Cloudflare D1
│   └── 激活码、授权期限、授权产品
│       └── 写入 → Cloudflare D1
├── 用户启动 Launcher
│   ├── 激活码、设备 ID、设备公钥
│   │   └── 请求 → Cloudflare Worker
│   │       └── 查询授权和设备绑定状态 → Cloudflare D1
│   │           └── 返回 Ed25519 签名授权文件 → Launcher
│   └── 保存授权文件和设备信息
│       └── 写入 → 本机 WaveDAQ-Launcher 数据目录
├── Launcher 查询产品
│   └── 查询最新 Release → Cloudflare Worker
│       └── 读取产品仓库最新 Release → GitHub
│           └── 返回当前平台安装包、版本和 SHA-256 → Launcher
├── Launcher 下载产品
│   └── 下载请求 → Cloudflare Worker
│       └── 再次读取并校验最新 GitHub 资产 → GitHub
│           └── 代理安装包 → Launcher
│               └── SHA-256 校验、保存、安装并启动 → 本地产品软件
└── 产品软件启动
    ├── 读取本地授权和设备密钥 → 本机数据目录
    └── 离线校验签名、产品 ID、平台和授权期限 → 产品启动流程
```

三个部分是：

- WaveDAQ-Launcher：Qt 桌面启动器，负责设备激活、授权保存、产品选择、安装和启动。
- 各个产品项目：独立维护业务软件，并提供对应平台的 GitHub Release 安装包。
- Cloudflare：授权 API、管理后台和 D1 数据库，负责在线授权、设备绑定和 Release 信息。

版本号只属于 GitHub Release 的安装信息，不属于授权配置。Worker 在线读取产品仓库的最新 Release，并匹配 macos-arm64、macos-x64 或 windows-x64 资产。

### 二、详细项目结构

```
WaveDAQ-License-System/
├── .github/workflows/build-launcher.yml # Launcher 发布工作流
├── launcher/                            # WaveDAQ-Launcher
│   ├── src/main.py                      # 图形程序入口
│   ├── src/gui.py                       # 激活、产品列表、下载和启动界面
│   ├── src/api_client.py                # 激活、刷新、Release 和下载请求
│   ├── src/config.py                    # Worker URL 和服务器公钥
│   ├── src/device_identity.py           # 设备 Ed25519 密钥和机器码绑定
│   ├── src/license_verifier.py          # Launcher 授权校验
│   ├── src/local_storage.py             # 授权、缓存和安装记录
│   ├── src/release_downloader.py        # 下载和 SHA-256 校验
│   ├── src/software_installer.py        # 安装包打开和产品启动
│   ├── tests/                           # Launcher 测试
│   ├── installer/WaveDAQ-Launcher.iss   # Windows 安装程序配置
│   └── Launcher.spec                    # PyInstaller 配置
├── assets/                              # 发布图标和项目展示图片
│   ├── app.icns                          # macOS 应用图标
│   ├── app.ico                           # Windows 应用图标
│   └── WaveDAG.png                       # WaveDAQ 界面图
├── license_sdk/                         # 产品侧可复制的离线验证模块
│   ├── __init__.py
│   ├── config.py                        # 产品 ID 和服务器公钥
│   ├── local_crypto.py                  # 机器码绑定的本地加密
│   └── verifier.py                      # 签名、设备、期限、平台校验
├── cloudflare/
│   ├── package.json                     # Cloudflare 子项目脚本
│   ├── worker/
│   │   ├── src/index.ts                 # Worker 路由和 API
│   │   ├── src/crypto.ts                # SHA-256、Ed25519 和激活码加密
│   │   ├── src/http.ts                  # 管理员会话和响应工具
│   │   ├── src/releases.ts              # GitHub Release 平台匹配
│   │   ├── src/types.ts                 # Worker 类型
│   │   ├── migrations/                  # D1 结构迁移
│   │   ├── tests/                       # Worker 测试
│   │   ├── package.json                 # Worker 依赖和测试脚本
│   │   ├── package-lock.json
│   │   ├── wrangler.toml                # Worker、D1 和静态资源配置
│   │   └── .dev.vars.example            # 本地 Secret 示例
│   ├── admin/
│   │   ├── src/main.tsx                 # React 管理后台入口和页面
│   │   ├── src/styles.css               # 管理后台样式
│   │   ├── index.html                   # Vite 页面入口
│   │   ├── package.json                 # 管理后台依赖和构建脚本
│   │   └── tsconfig.json
│   ├── admin/dist/                      # npm run build 生成，部署时供 Worker 托管
│   ├── shared/license-schema.json       # 离线授权文件结构
│   └── tools/                           # 密钥、激活码和密码工具
├── .gitignore
├── logo.png
└── README.md
```

WaveDAQ 等具体产品在独立仓库维护。产品仓库只需复制 license_sdk，不需要复制整个验证系统。

### 三、D1 数据库结构

| 表 | 用途 | 主要字段 |
|---|---|---|
| products | 产品目录 | `id`、`name`、`description`、`github_repository`、`status`、`is_frozen`、`created_at` |
| licenses | 激活码和授权状态 | `id`、`name`、`code_hash`、`code_ciphertext`、`status`、`term`、`expires_at`、`is_frozen`、`created_at` |
| license_products | 激活码与产品关系 | `license_id`、`product_id` |
| devices | 设备身份 | `id`、`public_key`、`fingerprint`、`status`、`created_at`、`last_seen_at` |
| activations | 激活码与设备绑定 | `license_id`、`device_id`、`activated_at` |
| request_nonces | 防止设备请求重放 | `nonce`、`device_id`、`created_at` |
| admin_login_attempts | 管理员登录限流 | `client_hash`、`failures`、`first_failed_at`、`last_failed_at`、`blocked_until` |

license_products 只保存授权和产品的关系。产品版本、平台安装包和 SHA-256 都在请求时直接从该产品 GitHub 仓库的最新 Release 解析，不写入 D1。产品版本由 GitHub Release 的 tag_name 决定，授权只控制产品。d1_migrations 是迁移记录表，不应手动修改。

### 四、开放 API

设备请求需要以下 Header：

```
x-device-id
x-device-timestamp
x-device-nonce
x-device-signature
```

设备签名内容：

```
{HTTP_METHOD}\\n{PATH}\\n{license_id}\\n{device_id}\\n{timestamp}\\n{nonce}
```

#### 1. 设备激活

```http
POST /api/activate
Content-Type: application/json
```

请求字段：activation_code、device_id、device_public_key、fingerprint。返回签名的 license 授权文件。

#### 2. 获取产品和最新 Release

```http
GET /api/releases?license_id=lic_xxx
```

需要设备签名 Header。返回授权产品、当前平台的最新 Release、版本、文件名、SHA-256 和下载地址。

#### 3. 刷新授权

```http
POST /api/license/refresh?license_id=lic_xxx
```

需要设备签名 Header，返回最新授权文件，用于同步冻结、撤销和期限变化。

#### 4. 下载产品安装包

```http
GET /api/download/{release_id}?license_id=lic_xxx
```

需要设备签名 Header。Worker 检查授权产品、平台、GitHub 资产来源后代理下载。

#### 5. 管理员登录和管理 API

```http
POST /api/admin/login
Content-Type: application/json
```

请求：

```json
{ "password": "管理员密码" }
```

成功后返回 HttpOnly Session Cookie。

管理 API 需要该 Cookie：

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | /api/admin/products | 创建产品 ID、名称、仓库和说明 |
| GET | /api/admin/products | 查询产品 |
| PATCH | /api/admin/products/{id} | 修改仓库和说明 |
| DELETE | /api/admin/products/{id} | 删除或归档产品 |
| POST | /api/admin/licenses | 创建激活码并选择产品 |
| GET | /api/admin/licenses | 查询授权 |
| GET | /api/admin/licenses/{id}/code | 查看激活码 |
| PATCH | /api/admin/licenses/{id} | 修改授权期限 |
| POST | /api/admin/licenses/{id}/revoke | 撤销授权 |
| POST | /api/admin/products/{id}/freeze | 冻结产品 |
| POST | /api/admin/products/{id}/unfreeze | 解冻产品 |
| POST | /api/admin/licenses/{id}/freeze | 冻结授权 |
| POST | /api/admin/licenses/{id}/unfreeze | 解冻授权 |
| GET | /api/admin/devices | 查询设备 |
| POST | /api/admin/devices/{id}/unbind | 解除设备绑定 |

### 五、配置自己的 Cloudflare 服务

#### 1. 创建 D1 和修改 Worker 配置

```bash
cd cloudflare/worker
npm install
npx wrangler login
npx wrangler d1 create your-license-database
```

将返回的数据库 ID、名称和自己的 Worker 名称写入 cloudflare/worker/wrangler.toml：

```toml
name = "your-license-worker"
main = "src/index.ts"
compatibility_date = "近期日期"

[[d1_databases]]
binding = "DB"
database_name = "your-license-database"
database_id = "your-d1-database-id"
migrations_dir = "migrations"

[assets]
directory = "../admin/dist"
not_found_handling = "single-page-application"
```

#### 2. 生成签名密钥

```bash
python ../tools/generate_signing_key.py
npx wrangler secret put LICENSE_SIGNING_PRIVATE_KEY
```

私钥只写入 Cloudflare Secret。公钥写入 Launcher 的 launcher/src/config.py 和每个产品的 license_sdk/config.py。签名私钥不能提交 GitHub。

#### 3. 配置管理员和 GitHub Token

```bash
python ../tools/set_admin_password.py
npx wrangler secret put ADMIN_PASSWORD_HASH
openssl rand -hex 32
npx wrangler secret put ADMIN_TOKEN
npx wrangler secret put GITHUB_TOKEN
```

GITHUB_TOKEN 使用具有 Release 读取权限的 GitHub Token。真实密码、Token 和私钥只使用 Secret 保存。

#### 4. 初始化和发布 Cloudflare 服务

```bash
cd cloudflare/admin
npm install
npm run build

cd ../worker
npx wrangler d1 migrations apply your-license-database --remote
npx wrangler deploy
```

部署完成后，将 Worker 输出的 HTTPS 地址写入 Launcher 的 launcher/src/config.py：

```python
API_URL = "https://your-license-worker.your-subdomain.workers.dev"
```

然后重新构建 Launcher 和产品。部署后台时必须先执行 npm run build，否则 Worker 的静态资源仍是旧版本。

#### 5. 本地开发

```bash
cd cloudflare/admin
npm run build
cd ../worker
npx wrangler dev
```

本地 Secret 放在 cloudflare/worker/.dev.vars，该文件已被 Git 忽略；生产环境使用 wrangler secret put。

### 六、运行目录

Launcher 和所有产品共用 WaveDAQ-Launcher 用户数据目录。

macOS：

```
~/Library/Application Support/WaveDAQ-Launcher/
├── device.json
├── license.json
├── licenses/
├── catalogs/
├── installations.json
├── downloads/
└── revoked_licenses.json
```

Windows：

```
%APPDATA%\\WaveDAQ-Launcher\\
├── device.json
├── license.json
├── licenses\\
├── catalogs\\
├── installations.json
├── downloads\\
└── revoked_licenses.json
```

Linux：

```
~/.config/WaveDAQ-Launcher/
├── device.json
├── license.json
├── licenses/
├── catalogs/
├── installations.json
├── downloads/
└── revoked_licenses.json
```

安装包实际保存为：

`<系统数据目录>/WaveDAQ-Launcher/downloads/<product_id>/<version>/<file_name>`。
`installations.json` 保存已下载产品的版本、平台、安装包路径和启动路径；macOS 产品的默认启动路径由 Release 元数据提供，Windows 产品默认直接启动下载后的文件。Launcher 不把产品安装到自己的 Python 或 Conda 环境中。

设备私钥、授权文件和防时间回拨数据不访问 macOS Keychain、Windows Credential Manager 或 Linux Secret Service，而是使用本地机器码派生密钥加密后保存在应用数据目录中。Launcher 启动时先校验机器码；激活完成后，Launcher 和产品默认使用本地签名授权离线启动，只有激活、刷新和下载操作需要联网。

### 七、在其他软件中接入验证模块

复制根目录 license_sdk/ 到目标产品：

```
目标产品/
├── license_sdk/
│   ├── __init__.py
│   ├── config.py
│   └── verifier.py
└── main.py
```

只修改 license_sdk/config.py：

```python
PRODUCT_ID = "your-product-id"
SERVER_PUBLIC_KEY = "your-server-public-key"
```

在产品真正的主入口调用：

```python
from license_sdk import LicenseError, require_valid_license

try:
    require_valid_license()
except LicenseError as exc:
    show_license_error(str(exc))
    raise SystemExit(1)

start_application()
```

产品 ID 必须与管理后台登记的 ID 完全一致。产品不需要配置版本号、数据目录名或密钥环服务名。产品发布时，需要在对应 GitHub 仓库的 Release 中提供可识别的 macOS ARM、macOS Intel 或 Windows x64 安装包。
