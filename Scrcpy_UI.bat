@echo off
cd /d "%~dp0"
python "%~dp0scrcpy_ui.py"
if errorlevel 1 py -3 "%~dp0scrcpy_ui.py"
