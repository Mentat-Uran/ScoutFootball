@echo off
setlocal

REM Single-port LAN launcher for ScoutFootball on Windows.
REM Usage:
REM   scripts\start-lan.bat
REM   scripts\start-lan.bat 8080

set PORT=%~1
if "%PORT%"=="" set PORT=8000

cd /d "%~dp0.."

echo ==========================================
echo   ScoutFootball LAN Deployment
echo ==========================================
echo.
echo Port: %PORT%
echo.

for /f %%A in ('powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $_.IPAddress -match '^(192\\.168\\.|10\\.|172\\.(1[6-9]|2[0-9]|3[0-1])\\.)' -and $_.PrefixOrigin -ne 'WellKnown' } ^| Select-Object -First 1 -ExpandProperty IPAddress)"') do (
    set LAN_IP=%%A
    goto :ip_found
)

:ip_found
if defined LAN_IP (
    set LAN_IP=%LAN_IP: =%
    echo Expected LAN URL: http://%LAN_IP%:%PORT%
) else (
    echo LAN IP could not be detected automatically.
    echo Run ipconfig and use your current IPv4 address manually.
)
echo.

echo Ensuring dependencies are ready...
call uv sync
if errorlevel 1 goto :fail

echo Opening Windows Firewall port %PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "if (-not (Get-NetFirewallRule -DisplayName 'ScoutFootball %PORT%' -ErrorAction SilentlyContinue)) { New-NetFirewallRule -DisplayName 'ScoutFootball %PORT%' -Direction Inbound -Action Allow -Protocol TCP -LocalPort %PORT% | Out-Null }"
if errorlevel 1 (
    echo Firewall rule was not created automatically. You may need to allow Python/Uvicorn manually.
)

echo.
echo Starting server on 0.0.0.0:%PORT% ...
echo Open locally: http://127.0.0.1:%PORT%
if defined LAN_IP echo Share in campus LAN: http://%LAN_IP%:%PORT%
echo API docs: http://127.0.0.1:%PORT%/docs
echo.

call uv run python -m scoutfootball serve --host 0.0.0.0 --port %PORT%
goto :end

:fail
echo.
echo Startup failed.
exit /b 1

:end
endlocal
