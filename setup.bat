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

REM ─── Detect VS Code workspace root ─────────────────────────
REM VS Code can be opened at Upgraded/ or at Excalibur_Modernized/.
REM We detect the correct root by looking for .sln or .vscode folder.
REM Strategy: try WORKSPACE_DIR first, then its parent.
set VSCODE_ROOT=%WORKSPACE_DIR%
if exist "%WORKSPACE_DIR%.vscode" (
    set VSCODE_ROOT=%WORKSPACE_DIR%
    echo  [OK] VS Code workspace root detected: %WORKSPACE_DIR%
) else if exist "%WORKSPACE_DIR%..\Excalibur.sln" (
    REM Workspace is the parent (Excalibur_Modernized\)
    for %%I in ("%WORKSPACE_DIR%..") do set VSCODE_ROOT=%%~fI\
    echo  [OK] VS Code workspace root detected: !VSCODE_ROOT!
) else (
    REM Fallback: also install to parent just in case
    for %%I in ("%WORKSPACE_DIR%..") do set VSCODE_ROOT=%%~fI\
    echo  [!!] Could not detect VS Code workspace root.
    echo       Installing to both %WORKSPACE_DIR% and !VSCODE_ROOT!
)

REM ─── Generate mcp.json with absolute path ──────────────────
REM Using absolute path to mcp_server.py avoids ${workspaceFolder} issues
REM when users open different folders as workspace root in VS Code.
set MCP_SERVER_PATH=%AGENT_DIR%mcp_server.py
REM Convert backslashes to double-backslashes for JSON
set MCP_SERVER_JSON=%MCP_SERVER_PATH:\=\\%
set PYTHON_JSON=%PYTHON:\=\\%

REM Install to detected VS Code root
if not exist "!VSCODE_ROOT!.vscode" mkdir "!VSCODE_ROOT!.vscode"
(
echo {
echo   "servers": {
echo     "excalibur-agent": {
echo       "type": "stdio",
echo       "command": "%PYTHON_JSON%",
echo       "args": [
echo         "%MCP_SERVER_JSON%"
echo       ],
echo       "env": {
echo         "PYTHONIOENCODING": "utf-8"
echo       }
echo     }
echo   }
echo }
) > "!VSCODE_ROOT!.vscode\mcp.json"
echo  [OK] .vscode\mcp.json installed at !VSCODE_ROOT!.vscode\

REM Also install to Upgraded/.vscode/ if different from VSCODE_ROOT
if /I not "!VSCODE_ROOT!" == "%WORKSPACE_DIR%" (
    if not exist "%WORKSPACE_DIR%.vscode" mkdir "%WORKSPACE_DIR%.vscode"
    copy /Y "!VSCODE_ROOT!.vscode\mcp.json" "%WORKSPACE_DIR%.vscode\mcp.json" >nul
    echo  [OK] .vscode\mcp.json also installed at %WORKSPACE_DIR%.vscode\
)

REM Copy .github/copilot-instructions.md (to Upgraded/ — always the project root)
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
echo  Installed to:
echo    !VSCODE_ROOT!.vscode\mcp.json           (MCP Server config - absolute paths)
echo    %WORKSPACE_DIR%.github\copilot-instructions.md   (Copilot custom instructions)
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
echo    "In PD_BarCodePrint line 87 there is an IndexOutOfRangeException, diagnose it"
echo.
pause
