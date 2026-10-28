import os
import shutil
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone


class Command(BaseCommand):
    help = "SmartLib ma'lumotlar bazasini xavfsiz zaxira qilish (Zero Data Loss) va Telegramga yuborish."

    def add_arguments(self, parser):
        parser.add_argument(
            '--send-telegram',
            action='store_true',
            help="Zaxira faylini admin Telegram chatiga yuborish",
        )

    def handle(self, *args, **options):
        base_dir = str(settings.BASE_DIR)
        backups_dir = os.path.join(base_dir, 'backups', 'database')
        os.makedirs(backups_dir, exist_ok=True)

        now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_path = str(settings.DATABASES['default']['NAME'])

        if not os.path.isfile(db_path):
            self.stdout.write(self.style.WARNING(f"SQLite fayl topilmadi yoki tashqi PostgreSQL ishlatilmoqda: {db_path}"))
            return

        backup_file = os.path.join(backups_dir, f"smartlib_backup_{now_str}.sqlite3")

        # Zero Data Loss: SQLite Online Backup API (jonli bazani bloklamasdan to'liq zaxira oladi)
        try:
            src = sqlite3.connect(db_path)
            dst = sqlite3.connect(backup_file)
            src.backup(dst)
            dst.close()
            src.close()
            file_size_kb = round(os.path.getsize(backup_file) / 1024, 1)
            self.stdout.write(self.style.SUCCESS(f"[OK] Baza zaxiralandi: {backup_file} ({file_size_kb} KB)"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"[ERROR] Zaxiralashda xatolik: {exc}"))
            return

        # 14 kundan eski zaxiralarni avtomatik tozalash
        cutoff = datetime.now() - timedelta(days=14)
        for fname in os.listdir(backups_dir):
            if fname.startswith("smartlib_backup_") and fname.endswith(".sqlite3"):
                fpath = os.path.join(backups_dir, fname)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                    if mtime < cutoff:
                        os.remove(fpath)
                except Exception:
                    pass

        # Agar --send-telegram bayrog'i berilgan bo'lsa va bot token mavjud bo'lsa
        send_tg = options.get('send_telegram') or bool(os.environ.get('TELEGRAM_BACKUP_ON_RUN'))
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '').strip()
        admin_chat_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', '').strip()

        if send_tg and token and admin_chat_id:
            self.stdout.write("Telegram orqali zaxira yuborilmoqda...")
            try:
                self._send_file_to_telegram(token, admin_chat_id, backup_file, now_str)
                self.stdout.write(self.style.SUCCESS("[OK] Telegram orqali adminga yuborildi!"))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Telegramga yuborishda xatolik: {exc}"))

    def _send_file_to_telegram(self, token, chat_id, file_path, timestamp):
        boundary = '----SmartLibBoundary' + timestamp
        body = []

        # chat_id field
        body.append(f'--{boundary}'.encode('utf-8'))
        body.append(f'Content-Disposition: form-data; name="chat_id"'.encode('utf-8'))
        body.append(b'')
        body.append(str(chat_id).encode('utf-8'))

        # caption field
        caption = f"🛡️ <b>SmartLib Avtomatik Baza Zaxirasi</b>\n📅 Sana: {timezone.now().strftime('%d.%m.%Y %H:%M')}\n💾 Zero Data Loss kafolati"
        body.append(f'--{boundary}'.encode('utf-8'))
        body.append(f'Content-Disposition: form-data; name="caption"'.encode('utf-8'))
        body.append(b'')
        body.append(caption.encode('utf-8'))

        # parse_mode field
        body.append(f'--{boundary}'.encode('utf-8'))
        body.append(f'Content-Disposition: form-data; name="parse_mode"'.encode('utf-8'))
        body.append(b'')
        body.append(b'HTML')

        # document field
        filename = os.path.basename(file_path)
        body.append(f'--{boundary}'.encode('utf-8'))
        body.append(f'Content-Disposition: form-data; name="document"; filename="{filename}"'.encode('utf-8'))
        body.append(b'Content-Type: application/x-sqlite3')
        body.append(b'')
        with open(file_path, 'rb') as f:
            body.append(f.read())

        body.append(f'--{boundary}--'.encode('utf-8'))
        body.append(b'')

        payload = b'\r\n'.join(body)
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'Content-Length': str(len(payload)),
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
