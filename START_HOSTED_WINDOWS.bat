@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  python setup_smollm.py --hosted %*
) else (
  py -3 setup_smollm.py --hosted %*
)
if errorlevel 1 goto error
exit /b 0
:error
echo Startup failed. Python 3.11 or newer is required. See the error above.
pause
exit /b 1
