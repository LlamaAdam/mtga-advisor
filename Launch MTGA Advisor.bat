@echo off
title MTGA Advisor
color 0A

echo.
echo  ================================================
echo    MTGA Game Advisor - Starting up...
echo  ================================================
echo.

:: Change to the folder this .bat file lives in
cd /d "%~dp0"

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo  Install Python from https://python.org and try again.
    pause
    exit /b 1
)

:: Install / verify dependencies silently on first run
echo  Checking dependencies...
python -m pip install -q -r game_advisor\requirements.txt
if errorlevel 1 (
    echo  [WARN] Some dependencies may be missing - continuing anyway.
)

echo  Launching advisor...
echo.

:: Run the advisor; keep window open if it crashes so you can read the error
python game_advisor\main.py
if errorlevel 1 (
    echo.
    echo  ================================================
    echo    Advisor exited with an error (see above).
    echo  ================================================
    pause
)
