@echo off
setlocal
call "%~dp0ForgePY.cmd" --console %*
exit /b %ERRORLEVEL%
