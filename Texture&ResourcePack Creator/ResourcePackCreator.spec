# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Minecraft Texture & Resource Pack Creator
# Build with:  pyinstaller ResourcePackCreator.spec

import sys
from PyInstaller.utils.hooks import collect_data_files

# tkinterdnd2 requires its Tcl/Tk extension files bundled
dnd_datas = collect_data_files('tkinterdnd2')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=dnd_datas,
    hiddenimports=['tkinterdnd2'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ResourcePackCreator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window — GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # Set to 'icon.ico' if you add one
)
