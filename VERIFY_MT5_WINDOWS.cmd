@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "ORRERY_VERIFY_ONLY=0"
if /i "%~1"=="--verify-only" set "ORRERY_VERIFY_ONLY=1"
title ORRERY FX - Windows SIMULATED Verification
where py >nul 2>&1
if errorlevel 1 goto :missing
where curl.exe >nul 2>&1
if errorlevel 1 goto :missing
rem Never overwrite files beside this launcher. Refuse an existing temp directory.
set "ORRERY_VERIFY_DIR=%TEMP%\orrery-verify-%RANDOM%-%RANDOM%"
if exist "%ORRERY_VERIFY_DIR%" goto :failed
mkdir "%ORRERY_VERIFY_DIR%"
if errorlevel 1 goto :failed
cd /d "%ORRERY_VERIFY_DIR%"
if errorlevel 1 goto :failed
set "BASE=https://raw.githubusercontent.com/kosei131/orrery-mobile/06ca38ae1346f0dd16cb0da13942b033c28fa534"
echo Downloading pinned public sources into an isolated temporary folder...
call :download mt5_local_dashboard.py 6f39a34f052b3783867cb857ea98362f451f5db6e9e6e24811b27676ff12b01e
if errorlevel 1 goto :failed
call :download mt5_readonly.py c48b03f9263b6a2605451184a8e0d01f211eeb0d121127a57da51f6c07b4aad0
if errorlevel 1 goto :failed
call :download test_mt5_local_dashboard.py 5c4d350a4adc50d66196fb7ebcdd5dcaf6a21ff0631d4748a70cb15100db65d3
if errorlevel 1 goto :failed
call :download test_mt5_safety.py d2f37a6eabd492b9f00e040383f446f52b2be85e5da5789df7cf773f1d0df924
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
py -c "import hashlib,os,sys; from pathlib import Path; sys.exit(hashlib.sha256(Path(os.environ['ORRERY_VERIFY_FILE']).read_bytes()).hexdigest() != os.environ['ORRERY_VERIFY_HASH'])"
exit /b %errorlevel%

:missing
echo [ERROR] Install Python launcher and Windows curl first.
if "%ORRERY_VERIFY_ONLY%"=="0" pause
exit /b 1

:failed
echo [FAIL] Verification stopped. No MT5 connection was requested.
if "%ORRERY_VERIFY_ONLY%"=="0" pause
exit /b 1
