@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>nul
set "FORGEPY_HOME=%~dp0"
set "FORGEPY_APP=%FORGEPY_HOME%app\ForgePYStandalone.py"
set "PY_CMD="
where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py.exe -3"
)
if not defined PY_CMD (
  where python.exe >nul 2>nul
  if not errorlevel 1 (
    python.exe -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python.exe"
  )
)
if not defined PY_CMD goto :python_fail
%PY_CMD% "%FORGEPY_APP%" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo ForgePY exited with code %RC%.
  echo Run VerifyForgePY.cmd for package diagnostics or ForgePYConsole.cmd for fallback mode.
  echo.
  pause
)
exit /b %RC%
:python_fail
echo [FAIL] ForgePY requires Python 3.11 or newer with Tkinter.
pause
exit /b 1
