@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Foresight - PubCast Reach
set "PYTHONUTF8=1"
pushd "%~dp0"
if errorlevel 1 goto folder_error
if not exist "start_reach.py" goto incomplete
if not exist "run_reach.py" goto incomplete
if not exist "main.py" goto incomplete
if not exist ".reach-venv\Scripts\python.exe" goto system_python
".reach-venv\Scripts\python.exe" -c "import sys,struct; sys.exit(0 if sys.version_info >= (3,11) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 goto use_venv
:system_python
py -3.12 -c "import sys,struct; sys.exit(0 if struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 goto use_py312
py -3 -c "import sys,struct; sys.exit(0 if sys.version_info >= (3,11) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 goto use_py
python -c "import sys,struct; sys.exit(0 if sys.version_info >= (3,11) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 goto use_python
python3 -c "import sys,struct; sys.exit(0 if sys.version_info >= (3,11) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 goto use_python3
echo.
echo Reach could not find 64-bit Python 3.11 or newer.
echo This launcher checked py, python, and python3.
echo If Python is already installed, send a screenshot of this window.
echo Otherwise install 64-bit Python 3.12, then reopen this launcher.
goto failure
:use_venv
".reach-venv\Scripts\python.exe" -u "start_reach.py" %*
set "REACH_EXIT=%ERRORLEVEL%"
goto finished
:use_py312
py -3.12 -u "start_reach.py" %*
set "REACH_EXIT=%ERRORLEVEL%"
goto finished
:use_py
py -3 -u "start_reach.py" %*
set "REACH_EXIT=%ERRORLEVEL%"
goto finished
:use_python
python -u "start_reach.py" %*
set "REACH_EXIT=%ERRORLEVEL%"
goto finished
:use_python3
python3 -u "start_reach.py" %*
set "REACH_EXIT=%ERRORLEVEL%"
goto finished
:finished
if not "%REACH_EXIT%"=="0" goto failure
echo.
echo Reach has stopped.
pause
popd
exit /b 0
:incomplete
echo.
echo This is not the complete extracted Reach folder.
echo Right-click the ZIP, choose Extract All, then open the launcher there.
echo Keep OPEN_REACH_WINDOWS.bat beside start_reach.py, run_reach.py and main.py.
goto failure
:folder_error
echo Reach could not open its folder.
echo Extract the ZIP into a folder you can edit, then try again.
pause
exit /b 1
:failure
echo.
echo Startup failed. The error above is the part to send back.
echo If reach-startup.log was created, it is beside this launcher.
pause
popd
exit /b 1
