@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 (echo Cannot open the extracted PubCast folder.& pause& exit /b 1)
if exist ".reach-venv\Scripts\python.exe" (
  ".reach-venv\Scripts\python.exe" "tools\workbench_preflight.py"
) else (
  echo No prepared Reach environment found. Preparing dependencies first...
  call "OPEN_REACH_WINDOWS.bat" --check
  if errorlevel 1 (echo Dependency setup failed.& pause& popd& exit /b 1)
  ".reach-venv\Scripts\python.exe" "tools\workbench_preflight.py"
)
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo Preflight passed. You can now launch OPEN_REACH_WINDOWS.bat.) else (echo Preflight failed. Please keep the output above.)
pause
popd
exit /b %RESULT%
