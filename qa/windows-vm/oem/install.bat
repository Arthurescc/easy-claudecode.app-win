@echo off
setlocal

set OEMROOT=%~dp0
if not exist "%OEMROOT%logs" mkdir "%OEMROOT%logs"

echo [%DATE% %TIME%] OEM install hook started > "%OEMROOT%logs\install.log"
powershell -NoProfile -ExecutionPolicy Bypass -File "%OEMROOT%validate-easy-claudecode.ps1" >> "%OEMROOT%logs\install.log" 2>&1
echo [%DATE% %TIME%] OEM install hook finished >> "%OEMROOT%logs\install.log"

exit /b 0
