# Build & Packaging Guide

This guide covers turning the source into distributable Windows executables
and a single-file **Inno Setup** installer.

There are two stages:

1. **Compile the executables** with PyInstaller.
2. **Compile the installer** with Inno Setup, which bundles those
   executables, creates Start-menu/desktop shortcuts, and registers a daily
   Scheduled Task for the notifier.

---

## 0. Prerequisites

| Tool        | How to get it                                                        |
| ----------- | -------------------------------------------------------------------- |
| Python 3.9+ | <https://www.python.org/downloads/> (tick *Add python.exe to PATH*)  |
| winget      | Ships with Windows 10/11; otherwise install *App Installer*          |
| Inno Setup 6| <https://jrsoftware.org/isdl.php>                                    |
| (optional) UPX | <https://upx.github.io/> — shrinks the .exe; PyInstaller auto-uses it if on PATH |

Install the Python build dependencies into a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[build]"
```

---

## 1. One-shot: the build script

The simplest path — from the **project root**:

```powershell
# Executables only:
.\scripts\build.ps1

# Executables + installer, after wiping previous output:
.\scripts\build.ps1 -Clean -Installer
```

Outputs:

- `dist\Updater.exe`
- `dist\Update Notifier.exe`
- `dist\installer\WindowsSoftwareUpdater-Setup-<version>.exe` (with `-Installer`)

The remaining sections explain what the script does, so you can run the steps
by hand or in CI.

---

## 2. Compiling the executables (PyInstaller)

The build is driven by **spec files** in `packaging\`, which are more
reproducible than long command lines. From the project root:

```powershell
pyinstaller packaging\Updater.spec        --noconfirm
pyinstaller packaging\UpdateNotifier.spec  --noconfirm
```

Each spec is configured for a **one-file, windowed** build that bundles
`icon.ico`. The resulting `dist\Updater.exe` and `dist\Update Notifier.exe`
are fully self-contained.

> **Equivalent legacy one-liners** (kept for reference; the specs are
> preferred because they pin the `src` path and data files):
>
> ```powershell
> pyinstaller --onefile --noconsole --icon=icon.ico --add-data "icon.ico;." `
>     --paths src --name=Updater main.py
> pyinstaller --onefile --noconsole --icon=icon.ico --add-data "icon.ico;." `
>     --paths src --name="Update Notifier" notifier.py
> ```

### Verifying the build

```powershell
.\dist\Updater.exe          # should open the GUI and auto-scan
.\dist\"Update Notifier.exe" # should toast if updates exist, then exit
```

---

## 3. Compiling the installer (Inno Setup)

The installer is defined by [`packaging\installer.iss`](../packaging/installer.iss).
It expects the two executables to already exist in `dist\`.

### Option A — Inno Setup Compiler (GUI)

1. Launch **Inno Setup Compiler**.
2. `File ▸ Open…` → `packaging\installer.iss`.
3. Press **F9** (*Build ▸ Compile*).
4. The setup `.exe` is written to `dist\installer\`.

### Option B — command line (ISCC)

```powershell
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" packaging\installer.iss
```

### What the installer does

A **single setup** installs everything in one wizard:

- Installs `Updater.exe`, `Update Notifier.exe`, and `icon.ico` into
  `C:\Program Files\Windows Software Updater\`.
- Creates a Start-menu shortcut (and an optional desktop shortcut).
- If the user keeps the **"Start the update notifier automatically when I sign
  in"** option ticked (on by default), adds the notifier to the per-user
  autostart registry key
  (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`), so it **runs at
  every login** and quietly checks for updates in the background.
- Runs the notifier once immediately after install, so autostart is live
  without waiting for the next sign-in.
- On uninstall, removes the autostart entry, kills any running notifier, and
  deletes the per-user data directory under `%LOCALAPPDATA%`.

> **Why the Run key and not a Scheduled Task?** The request is "run on every
> login for the user who installed it." The per-user `Run` key is the native
> Windows mechanism for exactly that: it fires on each interactive sign-in,
> needs no elevation to fire, and is removed automatically on uninstall
> (`Flags: uninsdeletevalue`). A Scheduled Task would be the right tool only
> if you needed a fixed clock schedule (e.g. "every day at 10:00") or
> execution while no user is logged in.

### Customising

Edit the `#define` block at the top of `installer.iss`:

```iss
#define AppVersion      "1.0.0"   ; bump for each release
#define AppPublisher    "Your Name"
```

To run the notifier for **all** users instead of just the installer, change
the `[Registry]` root from `HKCU` to `HKLM` (the install already runs as
admin). To use a fixed daily schedule instead of login-startup, replace the
`[Registry]` entry with a `schtasks.exe /Create /SC DAILY …` line in `[Run]`.

---

## 4. Release checklist

1. Bump the version in **three** places (they should match):
   - `pyproject.toml` → `version`
   - `src/wsu/__init__.py` → `__version__`
   - `packaging/installer.iss` → `#define AppVersion`
2. `.\scripts\build.ps1 -Clean -Installer`
3. Smoke-test both `dist\*.exe` and install/uninstall the setup `.exe`.
4. (Optional) Code-sign the executables and the installer with `signtool`.
5. Tag the release and attach the setup `.exe`.

---

## Troubleshooting

| Symptom                                    | Fix                                                                 |
| ------------------------------------------ | ------------------------------------------------------------------- |
| `ModuleNotFoundError: wsu` during build    | Run PyInstaller from the project root so `--paths src` resolves.    |
| A console window flashes on launch         | Ensure `console=False` in the spec (it is by default).              |
| Tray icon missing                          | Confirm `icon.ico` is bundled (`--add-data "icon.ico;."`).          |
| `ISCC.exe not found`                       | Install Inno Setup 6, or pass its full path.                        |
| Antivirus flags the one-file exe           | Common with PyInstaller; code-signing reduces false positives.      |
| Scheduled task not created                 | The installer must run **as admin**; `schtasks /Create` needs it.   |
