@echo off
chcp 65001 >nul 2>&1
setlocal

rem ============================================================
rem  DSH Unlock Mode - One-click installer (double-click me)
rem
rem  Usage:
rem    Double-click       -> install + self-check
rem    With an argument   -> unlock-dsh.bat check|uninstall|dry-run|list
rem
rem  NOTE: This file is intentionally ASCII-only.
rem  cmd.exe parses .bat in the OEM codepage, so non-ASCII
rem  characters here would corrupt parsing on non-UTF8 systems.
rem  All Chinese output comes from the .ps1 instead.
rem ============================================================

set "PS1=%~dp0unlock-dsh.ps1"
set "ACTION=%~1"
if "%ACTION%"=="" set "ACTION=install"

if not exist "%PS1%" (
    echo [X] unlock-dsh.ps1 not found.
    echo     Keep this .bat in the same folder as unlock-dsh.ps1.
    pause
    exit /b 1
)

rem Prefer pwsh (PowerShell 7), fall back to powershell (5.1)
where pwsh >nul 2>&1
if %errorlevel%==0 (
    set "PSEXE=pwsh"
) else (
    set "PSEXE=powershell"
)

"%PSEXE%" -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %ACTION%

echo.
echo ============================================================
echo  Done.
echo ============================================================
pause
endlocal
