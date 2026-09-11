@echo off
rem Legacy compatibility alias; ForgePYConsole.cmd is authoritative.
call "%~dp0ForgePYConsole.cmd" %*
exit /b %ERRORLEVEL%
