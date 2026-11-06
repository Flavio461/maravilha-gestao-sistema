@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 (echo Falha: instale Python 3.12 ou superior. & pause & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 (echo Falha na instalacao das dependencias. & pause & exit /b 1)
echo.
echo Proximo passo: execute CRIAR_ADMIN.bat e depois INICIAR.bat
pause
