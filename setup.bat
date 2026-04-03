@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  setup.bat — One-time setup for Excalibur Forensic Agent
REM  Run this ONCE after cloning the repo into your Excalibur workspace.
REM
REM  Expected location: Upgraded\excalibur-agent\setup.bat
REM  This script installs deps + copies VS Code config files
REM  to the parent workspace so MCP + Copilot work automatically.
REM ============================================================

echo.
echo  ============================================================
echo   Excalibur Forensic Migration Agent - Setup
echo  ============================================================
echo.

REM ─── Resolve paths ──────────────────────────
set AGENT_DIR=%~dp0
REM Remove trailing backslash for parent calculation
set AGENT_DIR_CLEAN=%AGENT_DIR:~0,-1%
for %%I in ("%AGENT_DIR_CLEAN%") do set WORKSPACE_DIR=%%~dpI

REM 1. Check Python (try real python first, then known install path)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    echo  [OK] Python 3.12 found
) else (
    python --version >nul 2>&1
    if !ERRORLEVEL! == 0 (
        set PYTHON=python
        echo  [OK] Python found on PATH
    ) else (
        echo  [!!] Python not found.
        echo       Installing Python 3.12 via winget...
        winget install Python.Python.3.12 --silent
        set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    )
)

REM 2. Install dependencies
echo.
echo  [..] Installing Python dependencies...
%PYTHON% -m pip install -r "%AGENT_DIR%requirements.txt" --quiet
echo  [OK] Dependencies installed

REM 3. Install VS Code config files to workspace
echo.
echo  [..] Installing VS Code config files...

REM Copy .vscode/mcp.json
if not exist "%WORKSPACE_DIR%.vscode" mkdir "%WORKSPACE_DIR%.vscode"
copy /Y "%AGENT_DIR%vscode-config\mcp.json" "%WORKSPACE_DIR%.vscode\mcp.json" >nul
echo  [OK] .vscode\mcp.json installed

REM Copy .github/copilot-instructions.md
if not exist "%WORKSPACE_DIR%.github" mkdir "%WORKSPACE_DIR%.github"
copy /Y "%AGENT_DIR%vscode-config\copilot-instructions.md" "%WORKSPACE_DIR%.github\copilot-instructions.md" >nul
echo  [OK] .github\copilot-instructions.md installed

REM 4. Add agent folder to PATH for this session
set PATH=%PATH%;%AGENT_DIR%

REM 5. Summary
echo.
echo  ============================================================
echo   SETUP COMPLETE!
echo  ============================================================
echo.
echo  Installed to: %WORKSPACE_DIR%
echo    .vscode\mcp.json                  (MCP Server config)
echo    .github\copilot-instructions.md   (Copilot custom instructions)
echo.
echo  IMPORTANT: Set your GitHub token before using the agent:
echo.
echo    PowerShell:  $env:GITHUB_TOKEN = "ghp_YOUR_TOKEN"
echo    CMD:         set GITHUB_TOKEN=ghp_YOUR_TOKEN
echo.
echo  Or create excalibur-agent\.env with:  GITHUB_TOKEN=ghp_YOUR_TOKEN
echo.
echo  ─── CLI Usage ───
echo    excalibur-fix -C ClassName -b "error description"
echo.
echo  ─── Copilot Chat Usage ───
echo    Open VS Code, switch to Agent mode, and just ask:
echo    "En PD_BarCodePrint linea 87 hay un IndexOutOfRangeException, diagnosticalo"
echo.
pause
