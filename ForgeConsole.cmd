@echo off
setlocal
call "%~dp0Forge.cmd" --console %*
exit /b %ERRORLEVEL%
