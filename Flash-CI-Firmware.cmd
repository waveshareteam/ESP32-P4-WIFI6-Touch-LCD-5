@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Flash-CI-Firmware.ps1" %*
exit /b %ERRORLEVEL%
