@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m flask --app app create-admin
pause
