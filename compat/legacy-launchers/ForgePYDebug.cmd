@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>nul
set "FORGEPY_HOME=%~dp0"
set "FORGEPY_APP=%FORGEPY_HOME%app\ForgePYBootstrap.py"
echo ============================================================================
echo  ForgePY F60R375 BOOTSTRAP DIAGNOSTIC
 echo ============================================================================
echo  Root: %FORGEPY_HOME%
echo  Log : %FORGEPY_HOME%logs\bootstrap\forgepy-bootstrap-latest.log
echo ----------------------------------------------------------------------------
where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe "%FORGEPY_APP%" %*
  set "RC=%ERRORLEVEL%"
) else (
  py.exe -3 "%FORGEPY_APP%" %*
  set "RC=%ERRORLEVEL%"
)
echo.
echo ForgePY exited with code %RC%.
echo Bootstrap log: "%FORGEPY_HOME%logs\bootstrap\forgepy-bootstrap-latest.log"
pause
exit /b %RC%
