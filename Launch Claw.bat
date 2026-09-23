@echo off
setlocal
cd /d "%~dp0"

where node >nul 2>&1
if errorlevel 1 goto missing
where npm >nul 2>&1
if errorlevel 1 goto missing

if not exist "product\ui\node_modules\" (
  echo Installing the console. This happens once.
  pushd "product\ui"
  call npm install
  if errorlevel 1 exit /b 1
  popd
)

echo Norfront Claw is starting.
echo Leave this window open. Close it to stop.
echo http://127.0.0.1:5173
start "Claw browser" /min powershell -NoProfile -WindowStyle Hidden -Command "$ok=$false; foreach($i in 1..40){ try { Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173' -TimeoutSec 1 | Out-Null; $ok=$true; break } catch { Start-Sleep -Milliseconds 500 } }; if($ok){ Start-Process 'http://127.0.0.1:5173' }"
pushd "product\ui"
call npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
set EXITCODE=%ERRORLEVEL%
popd
exit /b %EXITCODE%

:missing
echo Install Node from https://nodejs.org and run this file again.
exit /b 1
