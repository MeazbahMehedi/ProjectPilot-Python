# Windows installer build

The release includes build files, not a prebuilt Windows installer. The application and workflows were verified on Linux; the Windows packaging path has not been executed in this environment.

## Build using GitHub Actions

1. Upload the extracted project's contents to the repository root, including `.github/workflows/windows-installer.yml`.
2. Open **Actions → Build Windows installer → Run workflow**.
3. Wait for the Windows job to finish.
4. Download the installer artifact and extract its `.exe`.
5. Run the installer. It creates a per-user program installation and offers a desktop shortcut and Start-menu entry.

The workflow runs only when manually dispatched. It does not publish a GitHub release or deploy a service. The Windows runner must have Inno Setup 6 available; the build script reports a clear error if it is missing.

## Build locally on Windows

- Python edition: Python 3.10+ with the Windows launcher, plus Inno Setup 6. The script installs PyInstaller from `requirements-build.txt`.
- Java edition: a full Windows JDK 17+ including `jpackage`, plus Inno Setup 6.
- For either edition, run `BUILD-WINDOWS-INSTALLER.bat`, or execute `tools/Build-WindowsInstaller.ps1` from PowerShell.

Python uses PyInstaller in onedir/windowed mode. Java uses jpackage to create a runtime-bundled app image. Inno Setup wraps the resulting folder in an installer. Build output is written under `installers/`; the recipe version is **3.0.1**.

Once a successful Windows build is produced, its runtime is bundled with the application. End users of that installer are not expected to install Python, Java or an IDE. Verify the resulting installer on the target Windows version before distributing it broadly.

The installer places program files below `%LOCALAPPDATA%/Programs/`. User workspace data is separate, below `%LOCALAPPDATA%/ProjectPilot/Python/`, and is retained on uninstall. Python and Java use separate data directories and incompatible workspace formats.

Installer files are not code-signed by this source package. The source/JAR launchers remain available for immediate use with an installed runtime.
