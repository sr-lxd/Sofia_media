@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    set "MEDIA_PYTHON=%~dp0.venv\Scripts\python.exe"
) else (
    set "MEDIA_PYTHON=python"
)
"%MEDIA_PYTHON%" tools\bootstrap.py
if errorlevel 1 exit /b 1
"%MEDIA_PYTHON%" run.py %*
set "MEDIA_RESULT=%ERRORLEVEL%"
endlocal & exit /b %MEDIA_RESULT%
