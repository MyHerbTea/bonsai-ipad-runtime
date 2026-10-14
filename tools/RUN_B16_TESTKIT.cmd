@echo off
setlocal
cd /d "%~dp0"
where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Windows PowerShell not found.
  pause
  exit /b 2
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_B16_TESTKIT_GUI.ps1"
set "CODE=%ERRORLEVEL%"
echo.
echo [RESULT] ExitCode=%CODE%. Read RESULTS for the unified evidence ZIP.
echo PASS is candidate EXPERIMENT_PASS only. The default remains B8.
pause
exit /b %CODE%
