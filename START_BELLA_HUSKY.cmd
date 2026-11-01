@echo off
setlocal
cd /d "%~dp0"
set "PORT=8765"
set "WALK_URL=http://127.0.0.1:%PORT%/static/world_walk.html?view=green_room/main&demo=husky&pads=0"
where py >nul 2>nul
if not errorlevel 1 goto use_py
where python >nul 2>nul
if not errorlevel 1 goto use_python
echo Python 3 was not found. Install Python, then run this launcher again.
pause
exit /b 1
:use_py
start "Bella Faux Pas local server" /D "%~dp0" cmd /k py -3 -m http.server %PORT% --bind 127.0.0.1
goto open_browser
:use_python
start "Bella Faux Pas local server" /D "%~dp0" cmd /k python -m http.server %PORT% --bind 127.0.0.1
:open_browser
timeout /t 2 /nobreak >nul
start "" "%WALK_URL%"
echo Opened Bella Faux Pas Studio with its real Green Room artwork and bundled Husky.
echo The separate server window keeps the world running. Close it to stop.
