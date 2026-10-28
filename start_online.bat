@echo off
chcp 65001 >nul
title SmartLib — Online & Wi-Fi Server (Kutubxonachi + Mobil Kitobxonlar)
color 0B

echo ============================================================================
echo   SMARTLIB — ONLINE SERVER VA MOBIL KITOBXONLAR TIZIMI
echo ============================================================================
echo.
echo  [1] Kompyuterda Kutubxonachi Paneli: http://127.0.0.1:8000/librarian/
echo  [2] Kompyuterda Admin Panel (Jazzmin): http://127.0.0.1:8000/admin/
echo  [3] Kompyuterda Skaner-Terminal:       http://127.0.0.1:8000/librarian/terminal/
echo.
echo  Lokal Wi-Fi va Global Internet (Cloudflare HTTPS) tunnel ishga tushirilmoqda...
echo ============================================================================
echo.

cd /d "%~dp0"
set "PY_CMD=python"
if exist "venv\Scripts\python.exe" set "PY_CMD=venv\Scripts\python.exe"

start "SmartLib Django Server" cmd /k "%PY_CMD% manage.py runserver 0.0.0.0:8000"

timeout /t 2 >nul
start "" "http://127.0.0.1:8000/librarian/"

echo Global Cloudflare HTTPS internet ssilkasi ochilmoqda (Telefonlar 4G/5G/Wi-Fi orqali kirishi uchun)...
if exist "tools\run_tunnel.py" (
    %PY_CMD% tools\run_tunnel.py
)
pause
