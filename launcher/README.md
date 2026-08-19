# WaveDAQ Launcher

负责设备身份生成、一次性激活、授权文件保存、软件包下载、校验和启动真实 WaveDAQ。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m src.main device
PYTHONPATH=. python -m src.main activate <activation-code>
PYTHONPATH=. python -m src.main verify
PYTHONPATH=. python -m src.main refresh
PYTHONPATH=. python -m src.main releases
PYTHONPATH=. python -m src.main download <release-id> <output-path>
PYTHONPATH=. python -m src.main launch <application-path>
```

正式构建前必须在 `src/config.py` 中固定 Worker URL 和服务器 Ed25519 公钥。生产程序不允许通过环境变量或命令行替换服务器公钥。

设备私钥保存在 macOS Keychain 或 Windows Credential Manager 中，`device.json` 不再保存明文私钥。CLI 已实现设备身份、激活、离线验证、联网刷新、版本查询和受控下载。

`release_downloader.py` 已提供下载和 SHA-256 校验能力，`software_installer.py` 提供跨平台启动入口。真实应用集成时，应在 WaveDAQ 创建窗口和 UDP socket 之前调用 `verify_license()`。
