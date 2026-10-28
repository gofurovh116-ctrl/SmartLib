@echo off
title SmartLib (PQ-9) - Yagona Kutubxona Axborot Tizimi
cd /d "D:\SmartLib"
echo [1/3] Ma'lumotlar bazasi zaxira nusxasi olinmoqda (Zero Data Loss)...
"D:\SmartLib\venv\Scripts\python.exe" tools\safe_backup.py
echo [2/3] Migratsiyalar va tizim butunligi tekshirilmoqda...
"D:\SmartLib\venv\Scripts\python.exe" manage.py migrate --noinput
echo [3/3] SmartLib 8000-portda ishga tushirilmoqda...
start "" "http://127.0.0.1:8000"
"D:\SmartLib\venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8000
pause
