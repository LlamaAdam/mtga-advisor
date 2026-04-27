@echo off
title MTGA Draft Helper
cd /d "%~dp0"
C:\Python314\python.exe main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo Error: the program exited with code %ERRORLEVEL%
    pause
)
