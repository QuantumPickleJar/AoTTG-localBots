@echo off
setlocal
set "ROOT=%~dp0"
py -3 "%ROOT%tools\recovery_preflight.py"
if errorlevel 1 python "%ROOT%tools\recovery_preflight.py"
echo.
echo This check reads files only. It does not launch or modify the game.
pause
