@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>nul
set "FORGEPY_APP=%~dp0app\ForgePYBootstrap.py"
where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe "%FORGEPY_APP%" --console %*
  exit /b %ERRORLEVEL%
)
where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 "%FORGEPY_APP%" --console %*
  exit /b %ERRORLEVEL%
)
echo [FAIL] No console Python 3 launcher is available.
pause
exit /b 1
