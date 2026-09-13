@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>nul
set "FORGEPY_HOME=%~dp0"
set "FORGEPY_APP=%FORGEPY_HOME%app\ForgePYBootstrap.py"

echo ============================================================================
echo  ForgePY DEBUG / FOREGROUND DIAGNOSTIC LAUNCHER
echo ============================================================================
echo Root: %FORGEPY_HOME%
echo.

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe "%FORGEPY_APP%" %*
  set "RC=%ERRORLEVEL%"
) else (
  where py.exe >nul 2>nul
  if errorlevel 1 (
    echo [FAIL] ForgePY requires Python 3.11 or newer with Tkinter.
    set "RC=1"
  ) else (
    py.exe -3 "%FORGEPY_APP%" %*
    set "RC=%ERRORLEVEL%"
  )
)

echo.
echo ForgePY diagnostic process exited with code %RC%.
echo Bootstrap log: "%FORGEPY_HOME%logs\bootstrap\forgepy-bootstrap-latest.log"
pause
exit /b %RC%
