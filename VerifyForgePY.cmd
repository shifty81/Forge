@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>nul
set "FORGEPY_HOME=%~dp0"
set "FORGEPY_APP=%FORGEPY_HOME%app\ForgePYBootstrap.py"
set "FORGEPY_GATE=%FORGEPY_HOME%tools\ForgePYGate.py"
where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe "%FORGEPY_APP%" --self-test %*
  if errorlevel 1 exit /b %ERRORLEVEL%
  python.exe "%FORGEPY_GATE%" quick
  exit /b %ERRORLEVEL%
)
where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 "%FORGEPY_APP%" --self-test %*
  if errorlevel 1 exit /b %ERRORLEVEL%
  py.exe -3 "%FORGEPY_GATE%" quick
  exit /b %ERRORLEVEL%
)
echo [FAIL] No console Python 3 launcher is available.
pause
exit /b 1
