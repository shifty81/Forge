@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>nul
set "FORGEPY_HOME=%~dp0"
set "FORGEPY_GUI=%FORGEPY_HOME%ForgePY.cmd"
set "FORGEPY_CLI=%FORGEPY_HOME%app\ForgeUnifiedCli.py"

if "%~1"=="" goto GUI
if /I "%~1"=="--help" goto CLI
if /I "%~1"=="-h" goto CLI
for %%G in (ui source vault project performance executable workspace patch command full build run apply-updates) do (
  if /I "%~1"=="%%G" goto CLI
)
goto GUI

:CLI
where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe "%FORGEPY_CLI%" %*
  exit /b %ERRORLEVEL%
)
where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 "%FORGEPY_CLI%" %*
  exit /b %ERRORLEVEL%
)
echo [FAIL] ForgePY CLI requires Python 3.11 or newer.
exit /b 1

:GUI
call "%FORGEPY_GUI%" %*
exit /b %ERRORLEVEL%
