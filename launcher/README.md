# WaveDAQ Launcher

负责设备身份生成、一次性激活、授权文件保存、软件包下载、校验和启动真实 WaveDAQ。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m src.main device
PYTHONPATH=. python -m src.main verify --server-public-key <public-key>
```

当前 CLI 已实现设备身份、激活、离线验证和版本清单查询。

`release_downloader.py` 已提供下载和 SHA-256 校验能力，`software_installer.py` 提供跨平台启动入口。真实应用集成时，应在 WaveDAQ 创建窗口和 UDP socket 之前调用 `verify_license()`。
