@echo off
setlocal
if "%~1"=="" (
  echo Drag a AICadetsM1WatchN.txt onto this batch file.
  pause
  exit /b 1
)
set "ROOT=%~dp0"
set "INPUT=%~1"
set "OUT=%~dpn1_report"
py -3 "%ROOT%tools\analyze_trace.py" "%INPUT%" --out "%OUT%"
if errorlevel 1 python "%ROOT%tools\analyze_trace.py" "%INPUT%" --out "%OUT%"
if errorlevel 1 (
  echo Analyzer failed. Check Python 3 installation and the selected trace file.
  pause
  exit /b 1
)
echo.
echo Results saved to: %OUT%
pause
