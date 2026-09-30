@echo off
title YouTube to MP3 Launcher

echo Launching web browser portal...
:: Opens the web browser tab immediately
start "" "http://127.0.0.1:5000"

echo.
echo Starting Python backend server...
echo ------------------------------------------
echo Keep this window OPEN while using the app!
echo ------------------------------------------
echo.

:: Executes the Python script directly in this window
python app.py

pause
