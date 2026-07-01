@echo off
echo ================================================
echo  MTGA Draft Helper - Setup
echo  Powered by 17Lands
echo ================================================
echo.

echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo ================================================
echo  SETUP CHECKLIST
echo ================================================
echo.
echo [1] Calibrate card overlay positions:
echo     - Open MTGA and navigate to a draft pick screen
echo     - Run:  python calibrate.py
echo     - Click the top-left corner of each card when prompted
echo     - Copy the output into draft_helper\config.py
echo.
echo [2] (Optional) Adjust draft_helper\config.py settings:
echo     - RATINGS_START_DATE: set to the current set's release date
echo     - OVERLAY_OPACITY: adjust overlay transparency
echo     - ARENA_LOG_PATH: only needed if MTGA is in a non-default location
echo.
echo [3] Run the overlay:
echo     python main.py
echo.
echo NOTE: No CSV download needed! Ratings are fetched automatically
echo       from 17Lands the first time you start a draft.
echo       They are cached locally for the rest of the day.
echo.
pause
