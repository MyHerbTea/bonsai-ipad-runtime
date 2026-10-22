@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist "python\python.exe" (
  echo 缺少同包便携 Python。请完整解压 GitHub building 产物。
  pause
  exit /b 2
)
"python\python.exe" -X utf8 "%~dp0ptq1_oneclick.py" %*
set "BONSAI_EXIT=%ERRORLEVEL%"
echo.
echo 测试程序已结束，报告位于 RESULTS\current。
pause
exit /b %BONSAI_EXIT%
