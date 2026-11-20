@echo off
REM One-time setup. Double-click this file.
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto nopython
echo Creating a private Python environment for this folder...
py -3 -m venv .venv
if errorlevel 1 goto failed
echo Installing the libraries (takes a minute)...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
if not exist ".env" copy ".env.example" ".env" >nul
echo.
echo Setup done. Notepad will open your .env file now.
echo Paste your Gemini key after GEMINI_API_KEY= and/or your Claude key after ANTHROPIC_API_KEY= then save and close Notepad.
echo.
pause
notepad ".env"
echo.
echo Testing with the sample garage (no API key needed for this test)...
".venv\Scripts\python.exe" run_takeoff.py --from-json examples\sample_garage_extraction.json --order-id SAMPLE
echo.
echo If you see "Done." above, you're ready. Drag a plan PDF onto takeoff.bat to run one.
pause
exit /b

:nopython
echo Python is not installed. Install it from https://www.python.org/downloads/
echo On the first installer screen, CHECK "Add python.exe to PATH". Then run this again.
pause
exit /b

:failed
echo Something went wrong above. Take a screenshot and send it to Claude.
pause
