@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>nul
set "FORGEPY_HOME=%~dp0"
set "FORGEPY_APP=%FORGEPY_HOME%app\ForgePYBootstrap.py"
rem Foreground diagnostic launcher. ForgePY.vbs is the preferred no-console GUI launcher.
where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe "%FORGEPY_APP%" %*
  set "RC=%ERRORLEVEL%"
  if not "%RC%"=="0" (echo. & echo [FAIL] ForgePY exited with code %RC%. & echo Bootstrap log: "%FORGEPY_HOME%logs\bootstrap\forgepy-bootstrap-latest.log" & pause)
  exit /b %RC%
)
where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 "%FORGEPY_APP%" %*
  set "RC=%ERRORLEVEL%"
  if not "%RC%"=="0" (echo. & echo [FAIL] ForgePY exited with code %RC%. & echo Bootstrap log: "%FORGEPY_HOME%logs\bootstrap\forgepy-bootstrap-latest.log" & pause)
  exit /b %RC%
)
echo [FAIL] ForgePY requires Python 3.11 or newer with Tkinter.
pause
exit /b 1
