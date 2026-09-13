@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>nul
set "FORGEPY_HOME=%~dp0"
set "FORGEPY_VBS=%FORGEPY_HOME%ForgePY.vbs"
set "FORGEPY_APP=%FORGEPY_HOME%app\ForgePYBootstrap.py"

rem Normal ForgePY launch is GUI-only. Project/build/runtime output belongs in the
rem embedded Project Console. ForgePY-Debug.cmd is the explicit foreground lane.
if exist "%FORGEPY_VBS%" (
  start "" /b wscript.exe "%FORGEPY_VBS%" %*
  exit /b 0
)

where pythonw.exe >nul 2>nul
if not errorlevel 1 (
  start "" /b pythonw.exe "%FORGEPY_APP%" %*
  exit /b 0
)

where pyw.exe >nul 2>nul
if not errorlevel 1 (
  start "" /b pyw.exe -3 "%FORGEPY_APP%" %*
  exit /b 0
)

echo [FAIL] ForgePY could not locate its no-console GUI launcher.
echo Bootstrap log: "%FORGEPY_HOME%logs\bootstrap\forgepy-bootstrap-latest.log"
echo Use ForgePY-Debug.cmd for foreground diagnostics.
exit /b 1
