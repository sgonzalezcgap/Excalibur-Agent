@echo off
REM ============================================================
REM  excalibur-fix.bat — Launcher for Excalibur Forensic Agent
REM  Usage: excalibur-fix -C ClassName -b "error description"
REM  Run from anywhere — it finds the agent automatically.
REM ============================================================

REM Find Python
where python >nul 2>&1
if %ERRORLEVEL% == 0 (
    set PYTHON=python
) else (
    REM Try common install paths
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    ) else (
        echo [ERROR] Python not found. Install Python 3.10+ from https://www.python.org
        echo         Or run: winget install Python.Python.3.12
        exit /b 1
    )
)

REM Resolve agent directory (where this .bat lives)
set AGENT_DIR=%~dp0

REM Check if deps are installed
%PYTHON% -c "import openai" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [SETUP] Installing dependencies for first time...
    %PYTHON% -m pip install -r "%AGENT_DIR%requirements.txt" --quiet
)

REM Check GITHUB_TOKEN
if "%GITHUB_TOKEN%"=="" (
    echo [ERROR] GITHUB_TOKEN not set.
    echo         Run:  set GITHUB_TOKEN=ghp_YOUR_TOKEN
    echo         Or:   $env:GITHUB_TOKEN = "ghp_YOUR_TOKEN"  ^(PowerShell^)
    exit /b 1
)

REM Run the agent — pass all arguments through
%PYTHON% "%AGENT_DIR%excalibur-fix.py" %*
