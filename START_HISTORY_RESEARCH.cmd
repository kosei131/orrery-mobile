@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "ORRERY_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%ORRERY_PYTHON%" (
  "%ORRERY_PYTHON%" mt5_local_dashboard.py --history-dir research_artifacts_20261101/public_xau_bars --research-results research_artifacts_20261101/lsr02_vhf03_crosschecked_history.json
) else (
  py -3.12 mt5_local_dashboard.py --history-dir research_artifacts_20261101/public_xau_bars --research-results research_artifacts_20261101/lsr02_vhf03_crosschecked_history.json
)
if errorlevel 1 echo [STOPPED] Check Python, acquired CSV files and the matching research report.
pause
