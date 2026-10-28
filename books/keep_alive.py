import os
import sys
import threading
import time
import urllib.request
import logging

logger = logging.getLogger('smartlib.keepalive')


def run_keep_alive_loop():
    """
    Render Free serveri 15 daqiqada uxlab qolmasligi uchun
    har 10 daqiqada (600 soniya) Renderning public domeniga
    tashqaridan HTTP GET so'rov yuborib turadi. Bu so'rov Renderning
    tashqi kirish proksisiga tushadi va bo'sh turish taymerini yangilaydi.
    """
    target_url = "https://smartlib-1-olyc.onrender.com/health/"
    # Boshlang'ich kutish (server to'liq ko'tarilishi uchun)
    time.sleep(30)

    while True:
        try:
            req = urllib.request.Request(
                target_url,
                headers={'User-Agent': 'SmartLib-24-7-KeepAlive/1.0'}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                code = resp.getcode()
                if code == 200:
                    logger.info("[KeepAlive] Render 24/7 ping OK: %s", target_url)
        except Exception as e:
            logger.warning("[KeepAlive] Render ping failed: %s", e)

        # Har 10 daqiqada bir marta (Render 15 daqiqada uxlashini to'xtatadi)
        time.sleep(600)


def start_keep_alive_thread():
    # Test yoki migratsiya paytida ortiqcha ishga tushmaslik
    if any(cmd in sys.argv for cmd in ('makemigrations', 'migrate', 'test', 'audit.py')):
        return
    # Lokal runserver reloaderida 2 marta ochilmasligi uchun
    if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
        return

    thread = threading.Thread(target=run_keep_alive_loop, daemon=True, name="SmartLibKeepAlive")
    thread.start()
