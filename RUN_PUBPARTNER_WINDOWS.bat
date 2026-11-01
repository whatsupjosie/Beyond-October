@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title PubPartner

echo.
echo ==========================================
echo   PubPartner - Alex Friend Layer
echo ==========================================
echo.

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set "BASE_PY=py -3"
) else (
  where python >nul 2>nul
  if NOT %ERRORLEVEL% EQU 0 (
    echo Python 3.10 or newer was not found.
    echo Install Python from python.org and select "Add Python to PATH".
    pause
    exit /b 2
  )
  set "BASE_PY=python"
)

%BASE_PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if NOT %ERRORLEVEL% EQU 0 (
  echo PubPartner requires Python 3.10 or newer.
  %BASE_PY% --version
  pause
  exit /b 2
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating PubPartner's private Python environment...
  %BASE_PY% -m venv .venv
  if NOT !ERRORLEVEL! EQU 0 (
    echo Could not create .venv. Confirm Python includes the venv module.
    pause
    exit /b 3
  )
)

set "PYTHON=%CD%\.venv\Scripts\python.exe"

"%PYTHON%" scripts\bootstrap_dependencies.py
if NOT %ERRORLEVEL% EQU 0 (
  echo.
  echo PubPartner could not install or verify dependencies inside .venv.
  pause
  exit /b 4
)

"%PYTHON%" run_pubpartner.py --preflight
if NOT %ERRORLEVEL% EQU 0 (
  echo.
  echo Preflight found a blocking issue.
  echo Report: data\pubpartner\preflight_latest.json
  pause
  exit /b 5
)

echo.
echo PubPartner is starting at http://127.0.0.1:8000/pubpartner
echo Only the friend layer will start. PubCast studio systems remain off.
echo Keep this window open. Press Ctrl+C here to stop PubPartner.
echo.
"%PYTHON%" run_pubpartner.py
set "EXITCODE=%ERRORLEVEL%"
echo.
echo PubPartner stopped with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
