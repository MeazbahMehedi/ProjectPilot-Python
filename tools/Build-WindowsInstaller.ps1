$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
py -3 -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Could not install the Windows build dependency." }
py -3 -m PyInstaller --noconfirm --clean --windowed --onedir --name ProjectPilot --icon assets/app.ico --add-data "projectpilot/seed.json;projectpilot" main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
$compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$iscc = if ($compiler) { $compiler.Source } else { "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) { throw "Install Inno Setup 6, then run this script again." }
& $iscc tools/installer.iss
if ($LASTEXITCODE -ne 0) { throw "Installer packaging failed." }
Write-Host "Installer created in installers/. The end user does not need Python, Java or an IDE."
