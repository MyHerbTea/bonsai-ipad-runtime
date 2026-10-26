@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0"
if errorlevel 1 exit /b 2
if not exist "python\python.exe" goto missing
"python\python.exe" -X utf8 -u "%~dp0q8_metal_b8.py" %*
set "BONSAI_EXIT=%ERRORLEVEL%"
goto finished
:missing
echo Extract the complete Build127 TestKit ZIP, including portable Python.
set "BONSAI_EXIT=2"
:finished
popd
echo Exit code: %BONSAI_EXIT%
echo Results are saved under RESULTS.
echo Press any key to close this window.
pause >nul
exit /b %BONSAI_EXIT%