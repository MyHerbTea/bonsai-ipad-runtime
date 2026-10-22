@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Bonsai PTQ1 Benchmark
pushd "%~dp0"
if errorlevel 1 goto directory_error
if not exist "python\python.exe" goto missing_python
if not exist "ptq1_oneclick.py" goto missing_script
"python\python.exe" -X utf8 -u "%~dp0ptq1_oneclick.py" %*
set "BONSAI_EXIT=%ERRORLEVEL%"
echo.
echo Exit code: %BONSAI_EXIT%
echo Reports, when generated: RESULTS\current
goto finished

:missing_python
echo Missing bundled Python. Extract the ENTIRE delivery ZIP first.
set "BONSAI_EXIT=2"
goto finished

:missing_script
echo Missing ptq1_oneclick.py. Extract the ENTIRE delivery ZIP first.
set "BONSAI_EXIT=2"
goto finished

:finished
popd
echo.
echo Press any key to close this window.
pause >nul
exit /b %BONSAI_EXIT%

:directory_error
echo Cannot open the delivery directory. Extract the ZIP to a local folder.
echo Press any key to close this window.
pause >nul
exit /b 2
