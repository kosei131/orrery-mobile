@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "ORRERY_VERIFY_ONLY=0"
if /i "%~1"=="--verify-only" set "ORRERY_VERIFY_ONLY=1"
title ORRERY FX - Windows SIMULATED Verification
where py >nul 2>&1
if errorlevel 1 goto :missing
where curl.exe >nul 2>&1
if errorlevel 1 goto :missing
where powershell.exe >nul 2>&1
if errorlevel 1 goto :missing
rem Never overwrite files beside this launcher. Refuse an existing temp directory.
set "ORRERY_VERIFY_DIR=%TEMP%\orrery-verify-%RANDOM%-%RANDOM%"
if exist "%ORRERY_VERIFY_DIR%" goto :failed
mkdir "%ORRERY_VERIFY_DIR%"
if errorlevel 1 goto :failed
cd /d "%ORRERY_VERIFY_DIR%"
if errorlevel 1 goto :failed
set "BASE=https://raw.githubusercontent.com/kosei131/orrery-mobile/1a01767d96756a5fc17bbd875c3b19aef567d940"
echo Downloading pinned public sources into an isolated temporary folder...
call :download mt5_local_dashboard.py 9fae0e02bd33b52afa25b536db2e426e643b874a48d51829ad955d28bf8dcff0
if errorlevel 1 goto :failed
call :download mt5_readonly.py c48b03f9263b6a2605451184a8e0d01f211eeb0d121127a57da51f6c07b4aad0
if errorlevel 1 goto :failed
call :download test_mt5_local_dashboard.py ee14b20b5ef41f34a42f40d25c33b34acc1e3ba11bc8ccc73c7e1ccc902641aa
if errorlevel 1 goto :failed
call :download test_mt5_safety.py 1663551c6be0e1cba7140a2a1016468aec4180b658e09859ed07f1cacffe5ab9
if errorlevel 1 goto :failed
py -m py_compile mt5_local_dashboard.py mt5_readonly.py test_mt5_local_dashboard.py test_mt5_safety.py
if errorlevel 1 goto :failed
py -m unittest -v test_mt5_local_dashboard.py test_mt5_safety.py
if errorlevel 1 goto :failed
echo [PASS] Offline tests passed. No MT5 connection or orders.
if "%ORRERY_VERIFY_ONLY%"=="1" exit /b 0
echo Open the private URL below on this PC. Do not record or share it.
py -u mt5_local_dashboard.py --test-data
if errorlevel 1 goto :failed
if "%ORRERY_VERIFY_ONLY%"=="0" pause
exit /b 0

:download
set "ORRERY_VERIFY_FILE=%~1"
set "ORRERY_VERIFY_HASH=%~2"
curl.exe --proto =https --tlsv1.2 --fail --location --silent --show-error --connect-timeout 15 --max-time 60 --retry 2 "%BASE%/%~1" --output "%~1"
if errorlevel 1 exit /b 1
powershell.exe -NoProfile -NonInteractive -Command "if ((Get-FileHash -LiteralPath $env:ORRERY_VERIFY_FILE -Algorithm SHA256).Hash -ne $env:ORRERY_VERIFY_HASH) { exit 1 }"
exit /b %errorlevel%

:missing
echo [ERROR] Install Python launcher, Windows curl and PowerShell first.
if "%ORRERY_VERIFY_ONLY%"=="0" pause
exit /b 1

:failed
echo [FAIL] Verification stopped. No MT5 connection was requested.
if "%ORRERY_VERIFY_ONLY%"=="0" pause
exit /b 1
