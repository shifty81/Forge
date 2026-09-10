@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>nul
set "FORGE_HOME=%~dp0"
set "FORGE_APP=%FORGE_HOME%app\ForgeStandalone.py"
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
%PY_CMD% "%FORGE_APP%" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo Forge exited with code %RC%.
  echo Run VerifyForge.cmd for package diagnostics or ForgeConsole.cmd for fallback mode.
  echo.
  pause
)
exit /b %RC%
:python_fail
echo [FAIL] Forge requires Python 3.11 or newer with Tkinter.
pause
exit /b 1
