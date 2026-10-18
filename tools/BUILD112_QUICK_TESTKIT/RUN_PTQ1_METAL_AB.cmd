@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_ptq1_metal_ab.ps1"
echo.
echo PTQ1 Metal A/B test completed. See the result ZIP path above.
pause
endlocal
