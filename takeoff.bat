@echo off
REM Drag a plan PDF onto this file, or double-click it and paste the path.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto nosetup
set "PDF=%~1"
if not "%PDF%"=="" goto haveit
set /p "PDF=Drag the plan PDF into this window and press Enter: "
set "PDF=%PDF:"=%"
:haveit
set "ENGINE="
set "PROJECT="
set "ORDER="
set /p "ENGINE=Which AI reads the plans? gemini / claude / both (Enter = gemini): "
if "%ENGINE%"=="" set "ENGINE=gemini"
set /p "PROJECT=Project name (press Enter to use the name on the plans): "
set /p "ORDER=Order / quote ID (optional, press Enter to skip): "
if "%PROJECT%"=="" (
  ".venv\Scripts\python.exe" run_takeoff.py "%PDF%" --engine %ENGINE% --order-id "%ORDER%"
) else (
  ".venv\Scripts\python.exe" run_takeoff.py "%PDF%" --engine %ENGINE% --project "%PROJECT%" --order-id "%ORDER%"
)
echo.
start "" "%~dp0output"
pause
exit /b

:nosetup
echo Run setup.bat first (double-click it).
pause
