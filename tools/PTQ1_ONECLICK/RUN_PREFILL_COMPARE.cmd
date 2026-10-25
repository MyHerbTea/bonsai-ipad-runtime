@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0"
if errorlevel 1 exit /b 2
if not exist "python\python.exe" goto missing
"python\python.exe" -X utf8 -u "%~dp0prefill_compare.py" %*
set "BONSAI_EXIT=%ERRORLEVEL%"
goto finished
:missing
echo Extract the ENTIRE Build124 delivery ZIP, including portable Python.
set "BONSAI_EXIT=2"
:finished
popd
echo Exit code: %BONSAI_EXIT%
echo Press any key to close this window.
pause >nul
exit /b %BONSAI_EXIT%
