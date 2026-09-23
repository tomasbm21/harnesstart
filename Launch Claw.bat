@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\product"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo Installing Python. This happens once.
  where winget >nul 2>&1
  if errorlevel 1 (
    echo Python is missing, so the app cannot install it.
    pause
    exit /b 1
  )
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  where py >nul 2>&1 && set "PY=py"
  if not defined PY where python >nul 2>&1 && set "PY=python"
  if not defined PY (
    echo Python is missing, so the app cannot install it.
    pause
    exit /b 1
  )
)

"%PY%" -m norfront_claw.boot
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" pause
exit /b %EXITCODE%
