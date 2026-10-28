# SmartLib — Online Server va 24/7 Bulutli Hosting Yo'riqnomasi

## 1. Hozirgi Kompyuterdan Global Online (`https://`) Serverni Yoqish
1. [start_online.bat](file:///D:/SmartLib/start_online.bat) faylini ikki marta bosing (yoki `python tools/run_tunnel.py` ni ishga tushiring).
2. Tizim avtomatik ravishda global `https://...lhr.life` manzilini oladi va uni `backups/public_url.txt` fayliga yozadi.
3. **Kompyuterda (Kutubxonachi / Admin uchun):**
   - **Kutubxonachi Paneli:** `http://127.0.0.1:8000/librarian/` *(«📲 Mobil Kitobxon QR» tugmasini bosib, kitobxonlarga telefon orqali skanerlash uchun QR-kodni ko'rsating)*
   - **Skaner-Terminal (Kiosk):** `http://127.0.0.1:8000/librarian/terminal/`
   - **Jazzmin Admin Paneli:** `http://127.0.0.1:8000/admin/`
4. **Telefonda (Oddiy Kitobxonlar uchun):**
   - Kitobxonlar QR-kodni skanerlab yoki `https://...` ssilka orqali kirib ro'yxatdan o'tadi (`Talaba`, `O'quvchi` yoki `Mustaqil kitobxon`).
   - Kitobxon **«Kitobni olish»** tugmasini bosganda **6-xonali tasdiqlash kodi** chiqadi va so'rov 4 soniya ichida kompyuterdagi Kutubxonachi ekraniga kelib tushadi.
   - Kutubxonachi kompyuterdan **«Tasdiqlash»** tugmasini bosmaguncha kitob berilmaydi!

---

## 2. Render.com Bulutli Serveriga 24/7 Bepul Joylash (Kompyuter o'chiq bo'lganda ham ishlashi uchun)
Loyiha ichida barcha kerakli fayllar tayyorlangan:
- `requirements.txt`
- `build.sh`
- `Procfile`
- `render.yaml`

### Qadamlar:
1. Loyihani GitHub'dagi shaxsiy repozitoriyangizga yuklang:
   ```bash
   git init
   git add .
   git commit -m "SmartLib Production Ready"
   git branch -M main
   git remote add origin https://github.com/SIZNING_LOGIN/smartlib.git
   git push -u origin main
   ```
2. [https://dashboard.render.com](https://dashboard.render.com) saytiga kiring va **New +** -> **Blueprint** (yoki **Web Service**) ni tanlang.
3. GitHub repozitoriyangizni ulang — Render avtomatik ravishda `render.yaml` faylini o'qiydi va serverni `https://smartlib-uz.onrender.com` manzilida 24/7 ishga tushiradi!

---

## 3. PythonAnywhere.com Serveriga 24/7 Bepul Joylash
1. [https://www.pythonanywhere.com](https://www.pythonanywhere.com) da bepul hisob oching va **Consoles -> Bash** ni oching.
2. Loyihani yuklab olib, virtual muhit yarating:
   ```bash
   git clone https://github.com/SIZNING_LOGIN/smartlib.git
   cd smartlib
   mkvirtualenv --python=/usr/bin/python3.10 smartlib-venv
   pip install -r requirements.txt
   python manage.py collectstatic --noinput
   python manage.py migrate
   ```
3. **Web** bo'limiga o'tib, **Add a new web app -> Manual configuration -> Python 3.10** ni tanlang.
4. **WSGI configuration file** ichiga quyidagini yozing:
   ```python
   import os
   import sys
   path = '/home/SIZNING_LOGIN/smartlib'
   if path not in sys.path:
       sys.path.append(path)
   os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
5. **Reload** tugmasini bosing — saytingiz `https://SIZNING_LOGIN.pythonanywhere.com` manzilida 24/7 ishga tushadi!
