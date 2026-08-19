# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("cryptography") + collect_submodules("keyring.backends") + ["PySide6.QtSvg"]

a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="WaveDAQ-Launcher", debug=False, strip=False, upx=True, console=False)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="WaveDAQ-Launcher")
    app = BUNDLE(coll, name="WaveDAQ-Launcher.app", bundle_identifier="com.lmdhq.wavedaq.launcher", info_plist={"CFBundleShortVersionString": "1.0.0", "NSHighResolutionCapable": True})
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="WaveDAQ-Launcher", debug=False, strip=False, upx=True, console=False, onefile=True)
