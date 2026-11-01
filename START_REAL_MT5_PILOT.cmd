@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ORRERY FX - DEMO Historical Data Pilot
cd /d "%~dp0"
if not exist "START_REAL_MT5_PILOT.py" (
  echo [ERROR] START_REAL_MT5_PILOT.py must be in the same folder.
  pause
  exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Windows Python launcher is missing. Install Python for Windows first.
  pause
  exit /b 1
)
echo Read-only MT5 DEMO historical pilot.
echo Requires a locally installed MetaTrader5 Python package and a logged-in DEMO terminal.
echo This will not log into MT5 or submit any trades.
py -3 "%~dp0START_REAL_MT5_PILOT.py"
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo [STOPPED] Pilot did not complete. Check the message above.
if "%RESULT%"=="0" echo [DONE] Inspect the output report; it is NOT a USD account backtest.
pause
exit /b %RESULT%
