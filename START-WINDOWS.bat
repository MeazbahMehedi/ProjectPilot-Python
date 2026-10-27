@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 main.py
) else (
    python main.py
)
if errorlevel 1 (
    echo Launch failed. Install Python 3.10 or newer with Tcl/Tk support.
    pause
)
