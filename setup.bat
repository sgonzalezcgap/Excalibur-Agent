@echo off
REM ============================================================
REM  setup.bat — One-time setup for Excalibur Forensic Agent
REM  Run this ONCE after cloning the repo.
REM ============================================================

echo.
echo  ============================================================
echo   Excalibur Forensic Migration Agent - Setup
echo  ============================================================
echo.

REM 1. Check Python
where python >nul 2>&1
if %ERRORLEVEL% == 0 (
    set PYTHON=python
    echo  [OK] Python found
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    echo  [OK] Python 3.12 found at %PYTHON%
) else (
    echo  [!!] Python not found.
    echo       Installing Python 3.12 via winget...
    winget install Python.Python.3.12 --silent
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
)

REM 2. Install dependencies
echo.
echo  [..] Installing Python dependencies...
%PYTHON% -m pip install -r "%~dp0requirements.txt" --quiet
echo  [OK] Dependencies installed

REM 3. Add agent folder to PATH for this session
set AGENT_DIR=%~dp0
set PATH=%PATH%;%AGENT_DIR%

REM 4. Remind about GITHUB_TOKEN
echo.
echo  ============================================================
echo   SETUP COMPLETE!
echo  ============================================================
echo.
echo  IMPORTANT: Set your GitHub token before using the agent:
echo.
echo    PowerShell:  $env:GITHUB_TOKEN = "ghp_YOUR_TOKEN"
echo    CMD:         set GITHUB_TOKEN=ghp_YOUR_TOKEN
echo.
echo  Or create an excalibur-agent\.env file with:
echo    GITHUB_TOKEN=ghp_YOUR_TOKEN
echo.
echo  Then run the agent:
echo    excalibur-fix -C ClassName -b "error description"
echo.
echo  Or use from Copilot Chat in VS Code (MCP tools auto-discovered):
echo    Open Copilot Chat and the excalibur-agent tools appear automatically.
echo.
echo  Examples:
echo    excalibur-fix -C PD_BarCodePrint -b "IndexOutOfRangeException" -L "PD_BarCodePrint.cs:87"
echo    excalibur-fix --list-skills
echo    excalibur-fix --scan-notes
echo.
pause
