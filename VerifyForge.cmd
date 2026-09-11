@echo off
rem Legacy compatibility alias; VerifyForgePY.cmd is authoritative.
call "%~dp0VerifyForgePY.cmd" %*
exit /b %ERRORLEVEL%
