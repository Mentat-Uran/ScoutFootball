@echo off
setlocal

REM Single-port LAN launcher for ScoutFootball on Windows.
REM Usage:
REM   scripts\start-lan.bat
REM   scripts\start-lan.bat 8080

set "SCOUTFOOTBALL_LAN_PORT=%~1"
if not defined SCOUTFOOTBALL_LAN_PORT set "SCOUTFOOTBALL_LAN_PORT=8000"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-lan.ps1"
exit /b %ERRORLEVEL%
