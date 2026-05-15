# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import (collect_submodules,collect_dynamic_libs,)

BASE_DIR = Path(os.environ.get("PYI_SPEC_DIR", os.getcwd())).resolve()

a = Analysis(
    [str(BASE_DIR.parent / "PythonScript" / "PythonScript.py")],
    pathex=[str(BASE_DIR)],
    binaries=collect_dynamic_libs("av"),
    datas=[],
    hiddenimports=(
        collect_submodules("av") +
        collect_submodules("pymediainfo")
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PythonScript',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
