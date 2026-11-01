@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ORRERY FX - Read-only DEMO Research Session
cd /d "%~dp0"
if not exist "orrery_research_session.py" (
  echo [STOPPED] Session source is missing from this folder.
  pause
  exit /b 1
)
if not defined LOCALAPPDATA (
  echo [STOPPED] Windows local data directory is unavailable.
  pause
  exit /b 1
)
if not exist "%LOCALAPPDATA%\ORRERYFX\research\settings\session.local.json" (
  echo [SETUP NEEDED] Prepare the private session settings first.
  echo See ORRERY_RESEARCH_SESSION_JA.md in this folder.
  echo No data capture or account calculation has started.
  pause
  exit /b 1
)
py -3.12 "%~dp0orrery_research_session.py" --config "%LOCALAPPDATA%\ORRERYFX\research\settings\session.local.json"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" echo [DONE] Modeled research snapshot saved. This is not verified trading profit.
if not "%RESULT%"=="0" echo [STOPPED] Check the fixed session state. No success is assumed.
echo No orders, network sharing or recurring tasks were started.
pause
exit /b %RESULT%
