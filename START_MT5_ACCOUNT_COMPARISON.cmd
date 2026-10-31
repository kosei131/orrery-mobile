@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ORRERY FX - DEMO Account Comparison
cd /d "%~dp0"
if not exist "START_MT5_ACCOUNT_COMPARISON.py" (
  echo [ERROR] Launcher source missing from this checkout.
  pause
  exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Install Python for Windows first.
  pause
  exit /b 1
)
py -3 "%~dp0START_MT5_ACCOUNT_COMPARISON.py"
set "RESULT=%ERRORLEVEL%"
echo.
echo This is a read-only research estimate. No orders are placed.
pause
exit /b %RESULT%
