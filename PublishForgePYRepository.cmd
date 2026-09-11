@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>nul
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0PublishForgePYRepository.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" pause
exit /b %RC%
