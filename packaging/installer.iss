; ============================================================================
;  Windows Software Updater — Inno Setup script
; ----------------------------------------------------------------------------
;  A single installer that ships BOTH executables:
;
;    * Updater.exe        — the main GUI application.
;    * Update Notifier.exe — a lightweight background checker.
;
;  The notifier is configured to run automatically at EVERY login (Windows
;  startup) via the per-user "Run" registry key, so the user is reminded when
;  updates are available without ever opening the app manually.
;
;  Prerequisites:
;    1. Build the executables first (they must exist in ..\dist):
;         pyinstaller packaging\Updater.spec        --noconfirm
;         pyinstaller packaging\UpdateNotifier.spec  --noconfirm
;       (or simply run:  scripts\build.ps1)
;    2. Install Inno Setup 6+:  https://jrsoftware.org/isdl.php
;
;  Compile:
;    - GUI:  open this file in the Inno Setup Compiler and press F9, or
;    - CLI:  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
;
;  Output:  ..\dist\installer\WindowsSoftwareUpdater-Setup-<version>.exe
; ============================================================================

#define AppName        "Windows Software Updater"
#define AppVersion      "1.0.0"
#define AppPublisher    "Abdullah Al Baki"
#define AppPublisherURL "https://github.com/abdullahal-baki"
#define AppSupportURL   "https://github.com/abdullahal-baki/windows-software-updater/issues"
#define AppUpdatesURL   "https://github.com/abdullahal-baki/windows-software-updater/releases"
#define AppCopyright    "Copyright (C) 2026 Abdullah Al Baki"
#define AppExeName      "Updater.exe"
#define NotifierExeName "Update Notifier.exe"
#define RunValueName    "WindowsSoftwareUpdaterNotifier"
#define AppId           "{{B1E8C0E2-9B4A-4C7E-9C2D-WSU0UPDATER01}}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppPublisherURL}
AppSupportURL={#AppSupportURL}
AppUpdatesURL={#AppUpdatesURL}
AppCopyright={#AppCopyright}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoCopyright={#AppCopyright}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=WindowsSoftwareUpdater-Setup-{#AppVersion}
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; A machine-wide install (Program Files) needs admin rights.
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; Ticked by default — this is the "set up the notifier automatically" option.
Name: "startupnotifier"; Description: "Start the update notifier automatically when I sign in (recommended)"; GroupDescription: "Background updates:"

[Files]
Source: "..\dist\{#AppExeName}";      DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\{#NotifierExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\icon.ico";                DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Run the notifier at every login for the installing user. Using the per-user
; HKCU Run key (rather than a Scheduled Task) means it launches on each sign-in
; and is removed cleanly on uninstall. uninsdeletevalue strips it automatically.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#RunValueName}"; \
    ValueData: """{app}\{#NotifierExeName}"""; \
    Flags: uninsdeletevalue; Tasks: startupnotifier

[Run]
; Launch the notifier once right after install so the autostart is "live"
; immediately, without waiting for the next sign-in. Only if the task is on.
Filename: "{app}\{#NotifierExeName}"; Description: "Run the update notifier now"; \
    Flags: nowait postinstall skipifsilent; Tasks: startupnotifier
; Offer to open the main app when installation completes.
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
; Make sure no notifier instance is left running before files are removed.
Filename: "{sys}\taskkill.exe"; Parameters: "/IM ""{#NotifierExeName}"" /F"; \
    Flags: runhidden; RunOnceId: "KillNotifier"

[UninstallDelete]
; Clean up the per-user state directory written at runtime.
Type: filesandordirs; Name: "{localappdata}\WindowsSoftwareUpdater"
