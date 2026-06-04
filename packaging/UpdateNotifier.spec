# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the background Update Notifier.

Build (from the project root):

    pyinstaller packaging/UpdateNotifier.spec --noconfirm

Produces ``dist/Update Notifier.exe`` (one-file, windowed). The notifier
launches ``Updater.exe`` from the same directory when its toast is clicked,
so both executables are installed side by side.
"""

import os

PROJECT_ROOT = os.path.abspath(os.getcwd())
SRC = os.path.join(PROJECT_ROOT, "src")
ICON = os.path.join(PROJECT_ROOT, "icon.ico")
VERSION_INFO = os.path.join(PROJECT_ROOT, "packaging", "version_info_notifier.txt")

a = Analysis(
    [os.path.join(PROJECT_ROOT, "notifier.py")],
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
    name="Update Notifier",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=ICON,
    version=VERSION_INFO,
)
