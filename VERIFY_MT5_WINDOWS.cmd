@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ORRERY FX - Windows DEMO Verification
echo ==============================================
echo ORRERY FX - LOCAL SECURITY VERIFICATION
echo TEST DATA ONLY / NO ORDERS / NO MT5 PASSWORDS
echo ==============================================
echo.
where py >nul 2>&1
if errorlevel 1 (
 echo [ERROR] Python launcher not found.
 echo Install Python from https://www.python.org/downloads/windows/
 pause
 exit /b 1
)
where curl.exe >nul 2>&1
if errorlevel 1 (
 echo [ERROR] Windows curl.exe not found.
 pause
 exit /b 1
)
set "BASE=https://raw.githubusercontent.com/kosei131/orrery-mobile/main"
echo [1/4] Downloading two public source files directly from the ORRERY GitHub repository...
curl.exe --fail --location --silent --show-error --retry 2 "%BASE%/mt5_local_dashboard.py" --output "mt5_local_dashboard.py"
if errorlevel 1 (
 echo [ERROR] Failed to download dashboard source.
 pause
 exit /b 1
)
curl.exe --fail --location --silent --show-error --retry 2 "%BASE%/test_mt5_local_dashboard.py" --output "test_mt5_local_dashboard.py"
if errorlevel 1 (
 echo [ERROR] Failed to download test source.
 pause
 exit /b 1
)
echo [2/4] Compiling Python scripts...
py -m py_compile "mt5_local_dashboard.py" "test_mt5_local_dashboard.py"
if errorlevel 1 (
 echo [ERROR] Python syntax check failed.
 pause
 exit /b 1
)
echo [3/4] Executing simulated-data integration and security tests...
py -m unittest -v test_mt5_local_dashboard.py
if errorlevel 1 (
 echo [FAIL] Tests failed. Dashboard will not start.
 pause
 exit /b 1
)
echo [PASS] Tests completed successfully on this PC.
echo [4/4] Starting localhost-only SIMULATED DATA dashboard.
echo Open the full private URL printed below in your Windows browser.
echo Stop with Ctrl+C. Never publish the URL.
py -u mt5_local_dashboard.py --test-data
pause
