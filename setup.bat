@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" tools\bootstrap.py
if errorlevel 1 exit /b 1
echo 安装完成。运行 start.bat 后打开 http://127.0.0.1:15001
endlocal
