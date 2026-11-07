@echo off
setlocal
py -3 "%~dp0tools\archive_m2_watcher.py" monitor --prune-verified
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
    echo.
    echo M2 watcher archival stopped with exit code %RESULT%.
    echo Review the manifest and resolve the reported blocker before playtesting.
)
pause
exit /b %RESULT%
