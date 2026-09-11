@echo off
setlocal
call "%~dp0ForgePY.cmd" --self-test %*
if errorlevel 1 exit /b %ERRORLEVEL%
py.exe -3 "%~dp0tools\ForgePYGate.py" quick 2>nul || python.exe "%~dp0tools\ForgePYGate.py" quick
exit /b %ERRORLEVEL%
