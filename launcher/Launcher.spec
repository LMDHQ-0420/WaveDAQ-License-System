# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("cryptography") + ["PySide6.QtSvg"]

a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=[],
    # Keep the brand mark in the launcher distribution.  The launcher release
    # is the validation product; individual products do not need this asset.
    datas=[("../logo.png", ".")],
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
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="WaveDAQ-Launcher", debug=False, strip=False, upx=True, console=False)
    coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name="WaveDAQ-Launcher")
