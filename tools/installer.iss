#define AppName "ProjectPilot"
#define AppVersion "3.0.1"
[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppId=ProjectPilot-Python-Desktop
DefaultDirName={localappdata}\Programs\{#AppName}-Python
PrivilegesRequired=lowest
OutputDir=..\installers
OutputBaseFilename=ProjectPilot-Python-3.0.1-Windows-Setup
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\ProjectPilot.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
[Files]
Source: "..\dist\ProjectPilot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\ProjectPilot (Python)"; Filename: "{app}\ProjectPilot.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\ProjectPilot (Python)"; Filename: "{app}\ProjectPilot.exe"; WorkingDir: "{app}"; Tasks: desktopicon
[Run]
Filename: "{app}\ProjectPilot.exe"; Description: "Open ProjectPilot"; Flags: nowait postinstall skipifsilent
