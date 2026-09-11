@echo off
rem Legacy compatibility alias; ForgePY.cmd is authoritative.
call "%~dp0ForgePY.cmd" %*
exit /b %ERRORLEVEL%
