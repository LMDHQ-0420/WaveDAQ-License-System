<p align="center">
  <img src="logo.png" width="120" alt="License System Logo"/>
</p>

<h1 align="center">WaveDAQ License System</h1>

<p align="center">面向多个桌面软件的授权、分发与离线校验系统</p>

<p align="center">
  <a href="https://github.com/LMDHQ-0420/WaveDAQ-License-System/releases">验证系统 Releases</a>
  · <a href="#技术报告">技术报告</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11"/>
  <img src="https://img.shields.io/badge/PySide6-Qt-41CD52?logo=qt" alt="PySide6"/>
  <img src="https://img.shields.io/badge/Cloudflare-Workers-F38020?logo=cloudflare&logoColor=white" alt="Cloudflare Workers"/>
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey" alt="Platforms"/>
</p>

WaveDAQ License System 是一个面向多个桌面软件的授权系统。它不限定某一个产品：管理员可以登记产品及其 GitHub 仓库，用户通过统一的启动器完成授权、安装和启动。

## 用户使用

### 获取验证软件

验证系统发行包位于 [GitHub Releases](https://github.com/LMDHQ-0420/WaveDAQ-License-System/releases)。请根据自己的操作系统下载对应的 `WaveDAQ-Launcher`，解压后直接启动图形程序。

### 获取激活码

激活码需要由管理员创建和分发。如需申请激活码、查询授权产品或处理设备绑定，请联系：

**sunyuxiang25@mails.ucas.edu.cn**

### 激活和使用

1. 启动 `WaveDAQ-Launcher`。
2. 输入获得的激活码，提交设备授权申请。
3. 激活成功后，启动器显示当前授权的产品。
4. 选择产品并执行安装或启动。
5. 启动器会按照当前电脑的平台匹配产品安装包，并在安装前校验文件完整性。
6. 安装完成后，可以从启动器打开已安装产品。

首次激活需要联网。激活成功后，授权文件保存在本机，产品可以按照授权规则离线启动；再次联网时，启动器可以同步授权状态和产品信息。

一个激活码只能绑定一个设备。更换电脑前，需要联系管理员解除原设备绑定。授权期限支持永久授权和自定义过期时间；自定义期限到期后，授权不能继续使用。

## 常见问题

### 激活码从哪里获得？

请联系 `sunyuxiang25@mails.ucas.edu.cn`，说明需要使用的产品和操作系统。

### 为什么激活时需要联网？

服务器需要确认激活码状态、授权产品、有效期和设备绑定关系，并签发本机授权。首次激活完成后，后续使用不要求每次联网。

### 一个激活码能在两台电脑上使用吗？

不能。一个激活码只允许绑定一个设备。如果需要更换设备，请联系管理员先解除原设备绑定。

### 离线时可以使用吗？

可以。完成首次激活后，启动器和产品使用本地签名授权进行校验。自定义期限授权仍会在本地按过期时间失效。

### 为什么看不到某个产品？

产品必须由管理员登记，且当前激活码必须包含该产品授权。请确认激活码、授权状态和产品信息，仍有问题时联系管理员。

### 启动器和产品分别是什么？

启动器是统一的授权与软件入口；产品是实际提供业务功能的桌面软件。一个启动器可以管理多个已授权产品。

### 如何反馈问题？

请将操作系统、启动器提示、产品名称和复现步骤发送至 `sunyuxiang25@mails.ucas.edu.cn`。不要在公开渠道提交激活码、管理员凭据或设备私钥。

## 技术报告

### 一、系统组成

系统由三个部分组成：

- `WaveDAQ-Launcher`：Qt 桌面启动器，负责设备激活、授权保存、产品选择、安装和启动。
- 各个产品项目：独立维护业务软件，并提供与产品平台对应的 GitHub Release 安装包。
- `Cloudflare`：授权 API、管理后台和 D1 数据库，负责产品、授权码和设备绑定的在线管理。

三者通过产品标识、GitHub 仓库信息和签名授权文件协作。启动器不绑定某一个具体产品，产品由服务端返回的授权和 Release 信息决定。

### 二、项目结构

```text
WaveDAQ-License-System/
├── .github/workflows/       # Launcher 项目配置
├── launcher/                # WaveDAQ-Launcher Qt 桌面程序
│   ├── src/                 # GUI、API、设备身份、本地授权与启动逻辑
│   ├── tests/               # Launcher 测试
│   └── Launcher.spec        # PyInstaller 配置
├── cloudflare/
│   ├── worker/              # Cloudflare Worker 与 D1 迁移
│   ├── admin/               # 管理后台
│   ├── shared/              # 前后端共享数据结构
│   └── tools/               # 维护工具
├── license_sdk/             # 可复制到其他产品的离线验证模块
├── .gitignore
└── README.md
```

各产品在独立项目中维护。验证系统只负责通用授权和分发协作，不把任何一个产品写死为系统唯一产品。

### 三、在其他桌面软件中接入验证模块

`license_sdk/` 是产品侧使用的通用验证代码。它不负责联网激活、不保存签名私钥，也不依赖某个具体产品的 GUI；它只读取启动器写入的本地设备身份和授权文件，并在产品启动前完成离线校验。它不是第三个软件，而是随产品源码一起编译进产品的代码模块。

#### 1. 复制模块

将以下目录完整复制到目标产品项目的入口文件旁边，并保持目录名为 `license_sdk`：

```text
目标产品/
├── license_sdk/
│   ├── __init__.py
│   ├── config.py
│   └── verifier.py
└── main.py
```

复制时以本项目根目录的 `license_sdk/` 为模板。目标产品需要独立提交这份代码，不能在运行时依赖验证系统源码路径。

#### 2. 修改产品配置

只修改目标产品中的 `license_sdk/config.py`：

```python
PRODUCT_ID = "your-product-id"
APP_VERSION = "1.0.0"
SERVER_PUBLIC_KEY = "Cloudflare Worker 使用的 Ed25519 公钥"

DATA_DIRECTORY_NAME = "WaveDAQ-Launcher"
KEYRING_SERVICE = "WaveDAQ License Device Key"
CLOCK_SERVICE = "WaveDAQ License Clock"
```

`PRODUCT_ID` 必须与管理后台登记的产品 ID 完全一致。产品 ID 创建后不能修改；产品名称只是显示文本。当前系统不在后台维护固定版本号，授权默认允许 `*`，启动器从产品 GitHub 仓库读取最新 Release，并根据平台匹配安装包。`APP_VERSION` 保留用于需要版本限制的产品；如果使用默认的 `*` 授权，它不会限制最新 Release。`SERVER_PUBLIC_KEY` 必须使用授权服务对应的公钥。签名私钥、管理员密码和 GitHub Token 不得放入产品项目。

#### 3. 在主入口强制验证

在创建主窗口、打开设备、启动服务或进入核心功能之前调用：

```python
from license_sdk import LicenseError, require_valid_license

try:
    require_valid_license()
except LicenseError as exc:
    show_license_error(str(exc))
    raise SystemExit(1)

start_application()
```

验证调用应当位于真正的程序入口，而不是只放在某个可绕过的设置页面。这样 PyInstaller 分析入口时会把 `license_sdk` 一起编译，发布包也会强制经过授权校验。

#### 4. 产品发布前检查

提交产品前，开发者需要确认：

1. 管理后台已经登记产品名称、产品 ID 和 GitHub 仓库。
2. 产品 `config.py` 使用了正确的产品 ID、版本号和服务器公钥。
3. 产品入口无论从源码还是打包程序启动，都会先调用 `require_valid_license()`。
4. Release 安装包名称能被授权服务识别，并包含目标系统对应的 macOS ARM、macOS Intel 或 Windows x64 资产。
5. 产品在已激活、未激活、过期、错误设备和离线状态下分别测试过。
6. 提交仓库前检查没有包含签名私钥、管理员凭据、GitHub Token、真实激活码或本机授权文件。

验证系统只需要产品的 GitHub 仓库链接和 Release 资产信息；产品不需要把业务代码提交到本项目。

### 四、三个系统如何配合

1. 管理员在后台登记产品 ID、产品名称、GitHub 仓库和授权规则，并生成激活码。
2. 启动器为当前设备生成设备身份，在线提交激活码和设备信息。
3. Cloudflare Worker 校验激活码，记录设备绑定，并签发经过 Ed25519 签名的授权文件。
4. 启动器保存授权文件，根据授权产品查询对应仓库的 Release，并匹配当前平台。
5. 启动器下载并校验产品安装包，然后保存安装记录并启动产品。
6. 产品启动时独立验证本地授权签名、产品标识、设备身份和有效期。

Cloudflare 负责在线状态，启动器和产品负责本地使用。产品不需要依赖启动器常驻；启动器也不需要为某个固定产品单独开发。

### 五、运行目录和服务端

启动器和产品使用统一的 `WaveDAQ-Launcher` 用户数据目录保存设备身份、授权文件、产品信息缓存、安装记录和下载文件。运行数据属于用户本机，不进入 Git 仓库。

Cloudflare 部分由 Worker、D1 和管理后台组成。Worker 提供授权接口，D1 保存产品、授权和设备绑定数据，后台用于管理员维护。生产环境的签名私钥和管理员凭据使用 Cloudflare Secret 管理。

### 六、维护边界

- 启动器维护通用授权入口、产品发现、安装和启动。
- 产品项目维护自身功能、平台适配和 Release 安装包。
- Cloudflare 维护在线授权状态、产品信息和设备绑定。

调整授权协议、签名公钥或共享数据格式时，需要同步检查启动器、产品和 Worker。
