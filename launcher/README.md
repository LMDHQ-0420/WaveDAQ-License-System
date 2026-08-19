# WaveDAQ Launcher

负责设备身份生成、一次性激活、授权文件保存、软件包下载、校验和启动真实 WaveDAQ。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m src.main
```

也可以从任意目录直接运行 Launcher 入口：

```bash
python /Users/lmdhq/WorkSpace/WaveDAQ-License-System/launcher/src/main.py
```

不带参数会打开图形化软件中心：首次进入显示激活码页面；激活后显示该密钥允许安装的软件；后续进入直接显示已安装程序，右下角可以新增密钥。
Launcher 只提供图形界面，不再提供命令行子命令。

正式构建前必须在 `src/config.py` 中固定 Worker URL 和服务器 Ed25519 公钥。生产程序不允许通过环境变量或命令行替换服务器公钥。

设备私钥保存在 macOS Keychain 或 Windows Credential Manager 中，`device.json` 不再保存明文私钥。Launcher 支持保存多个激活码对应的授权，并在启动具体软件前切换当前授权文件。

`release_downloader.py` 已提供下载和 SHA-256 校验能力，`software_installer.py` 提供跨平台启动入口。真实应用集成时，应在 WaveDAQ 创建窗口和 UDP socket 之前调用 `verify_license()`。
