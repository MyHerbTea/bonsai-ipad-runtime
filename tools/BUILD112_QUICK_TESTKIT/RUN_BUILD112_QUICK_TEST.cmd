@echo off
setlocal
cd /d "%~dp0"
where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Windows PowerShell is required.
  pause
  exit /b 2
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_build112_quick_test.ps1"
set "CODE=%ERRORLEVEL%"
echo.
echo [RESULT] ExitCode=%CODE%
echo Results are in the RESULTS folder.
pause
exit /b %CODE%
