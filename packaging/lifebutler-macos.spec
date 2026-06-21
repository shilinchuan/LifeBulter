# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from pathlib import Path


block_cipher = None
ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "app/assets"), "app/assets"),
    (str(ROOT / "resources/icon/LifeButler-icon.png"), "resources/icon"),
]
datas += collect_data_files("matplotlib")

hiddenimports = collect_submodules("PyQt6") + collect_submodules("matplotlib")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tests"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LifeButler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "resources/icon/LifeButler.icns"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LifeButler",
)

app = BUNDLE(
    coll,
    name="LifeButler.app",
    icon=str(ROOT / "resources/icon/LifeButler.icns"),
    bundle_identifier="com.lifebutler.desktop",
    info_plist={
        "CFBundleName": "LifeButler",
        "CFBundleDisplayName": "LifeButler",
        "CFBundleShortVersionString": "0.3.0",
        "CFBundleVersion": "0.3.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.productivity",
    },
)
