@echo off
setlocal
cd /d "%~dp0"
"%~dp0python\python.exe" "%~dp0build129_reasoning_api_smoke.py" --identity "%~dp0TestKitIdentity.json"
echo.
echo Results are preserved under RESULTS.
pause
endlocal
