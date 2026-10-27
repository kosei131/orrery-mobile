@echo off
setlocal
cd /d "%~dp0"
title ORRERY FX - Windows MT5 Verification
echo ==============================================
echo  ORRERY FX - LOCAL VERIFICATION
echo  DEMO ONLY / NO ORDERS / NO PASSWORD STORAGE
echo ==============================================
echo.
where py >nul 2>&1
if errorlevel 1 (
 echo [ERROR] Python launcher was not found.
 echo Install Python from https://www.python.org/downloads/windows/
 pause
 exit /b 1
)
if not exist "mt5_local_dashboard.py" (
 echo [ERROR] mt5_local_dashboard.py must be in this same folder.
 pause
 exit /b 1
)
if not exist "test_mt5_local_dashboard.py" (
 echo [ERROR] test_mt5_local_dashboard.py must be in this same folder.
 pause
 exit /b 1
)
echo [1/3] Checking Python...
py --version
echo.
echo [2/3] Running local simulated-data security tests...
py -m unittest -v test_mt5_local_dashboard.py
if errorlevel 1 (
 echo.
 echo [FAIL] Offline tests failed. MT5 will NOT be opened automatically.
 pause
 exit /b 1
)
echo.
echo [PASS] Offline tests passed on this Windows PC.
echo.
echo [3/3] Local dashboard test mode
echo Opening localhost-only dashboard with SIMULATED TEST DATA.
echo MT5 login is NOT used at this step.
echo Copy the private local URL printed below into a browser on this same PC.
echo Press Ctrl+C to stop.
echo.
py -u mt5_local_dashboard.py --test-data
pause
