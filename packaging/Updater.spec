# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows Software Updater GUI.

Build (from the project root):

    pyinstaller packaging/Updater.spec --noconfirm

Produces ``dist/Updater.exe`` (one-file, windowed, with the bundled icon).
"""

import os

PROJECT_ROOT = os.path.abspath(os.getcwd())
SRC = os.path.join(PROJECT_ROOT, "src")
ICON = os.path.join(PROJECT_ROOT, "icon.ico")
VERSION_INFO = os.path.join(PROJECT_ROOT, "packaging", "version_info.txt")

a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[SRC],
    binaries=[],
    datas=[(ICON, ".")],
    hiddenimports=[],
    hookspath=[],
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
    name="Updater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,           # windowed app, no console
    disable_windowed_traceback=False,
    icon=ICON,
    version=VERSION_INFO,
)
