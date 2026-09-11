@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================================================
echo  VAULT SAFE SELF-UPDATE / ROOT-DROP RECOVERY
echo ========================================================================
echo  Intake is temporarily restricted to this Vault application root.
echo  This allows an older Vault build to apply its own update even when the
echo  global Downloads folder contains malformed or historical patch archives.
echo.

set "VAULT_INTAKE_PATHS=%CD%"
where py >nul 2>&1
if errorlevel 1 (
  set "VAULT_PYTHON=python"
) else (
  set "VAULT_PYTHON=py -3"
)

%VAULT_PYTHON% "%CD%\app\PCCOperationHost.py" --root "%CD%" --operation patch-apply -- %VAULT_PYTHON% "%CD%\app\PCCAutoAdapter.py" patch-apply --root "%CD%"
set "VAULT_UPDATE_RC=%ERRORLEVEL%"

rem Do not leak root-only intake into the newly upgraded Vault process.  Normal
rem startup restores Downloads monitoring, but F21+ treats its rejections as
rem review items instead of project-gate failures.
set "VAULT_INTAKE_PATHS="

if not "%VAULT_UPDATE_RC%"=="0" (
  echo.
  echo [FAIL] Vault safe self-update exited %VAULT_UPDATE_RC%.
  echo        The application was not launched. Review the output above.
  pause
  exit /b %VAULT_UPDATE_RC%
)

echo.
echo [PASS] Root-drop update phase completed. Starting Vault normally...
if exist "%CD%\Vault.vbs" (
  start "" wscript.exe "%CD%\Vault.vbs"
  exit /b 0
)
%VAULT_PYTHON% "%CD%\app\VaultStandalone.py" --root "%CD%"
exit /b %ERRORLEVEL%
