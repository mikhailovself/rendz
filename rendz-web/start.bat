@echo off
chcp 65001 >nul
cd /d "%~dp0"
title rendz

where node >nul 2>nul
if errorlevel 1 (
    echo Node.js ne naiden. Ustanovi ego (besplatno) i zapusti etot fajl eshe raz:
    echo   https://nodejs.org   ^(knopka LTS^)
    echo ili v konsoli:  winget install OpenJS.NodeJS.LTS
    echo.
    pause
    exit /b
)

node server.js
echo.
echo Server ostanovlen. Esli vyshe est oshibka, skopiruj ee.
pause
