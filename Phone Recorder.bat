@echo off
cd /d "%~dp0"
python "%~dp0phone_recorder.py"
if errorlevel 1 py -3 "%~dp0phone_recorder.py"
