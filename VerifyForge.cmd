@echo off
setlocal
call "%~dp0Forge.cmd" --self-test %*
if errorlevel 1 exit /b %ERRORLEVEL%
py.exe -3 "%~dp0tools\ForgeGate.py" quick 2>nul || python.exe "%~dp0tools\ForgeGate.py" quick
exit /b %ERRORLEVEL%
