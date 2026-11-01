import hashlib
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

    MIN_BACKUPS_RETAINED = 10
    RETENTION_DAYS = 14

    def add_arguments(self, parser):
        parser.add_argument(
            '--send-telegram',
            action='store_true',
            help="Zaxira faylini admin Telegram chatiga yuborish",
        )

    @staticmethod
    def _compute_sha256(file_path):
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def _write_sha256_manifest(cls, backup_file):
        digest = cls._compute_sha256(backup_file)
        sha_file = f"{backup_file}.sha256"
        filename = os.path.basename(backup_file)
        with open(sha_file, 'w', encoding='utf-8') as sf:
            sf.write(f"{digest}  {filename}\n")
        return sha_file, digest

    def handle(self, *args, **options):
        base_dir = str(settings.BASE_DIR)
        backups_dir = os.path.join(base_dir, 'backups', 'database')
        os.makedirs(backups_dir, exist_ok=True)

        # Collision-proof microsecond naming (eliminates 1-second overwrite hazard)
        now_str = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        db_engine = settings.DATABASES['default'].get('ENGINE', '')
        db_path = str(settings.DATABASES['default']['NAME'])

        if 'sqlite' in db_engine and os.path.isfile(db_path):
            backup_file = os.path.join(backups_dir, f"smartlib_backup_{now_str}.sqlite3")
            tmp_file = f"{backup_file}.tmp"
            # Zero Data Loss: SQLite Online Backup API -> .tmp -> PRAGMA integrity_check -> atomic os.replace
            src = None
            dst = None
            try:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
                src = sqlite3.connect(db_path)
                dst = sqlite3.connect(tmp_file)
                src.backup(dst)
                integrity_row = dst.execute("PRAGMA integrity_check;").fetchone()
                integrity = integrity_row[0] if integrity_row else "failed"
                if str(integrity).lower() != "ok":
                    raise RuntimeError(f"Backup integrity check failed: {integrity}")
                dst.close()
                dst = None
                src.close()
                src = None

                os.replace(tmp_file, backup_file)
                self._write_sha256_manifest(backup_file)

                file_size_kb = round(os.path.getsize(backup_file) / 1024, 1)
                self.stdout.write(self.style.SUCCESS(f"[OK] Baza zaxiralandi: {backup_file} ({file_size_kb} KB)"))
            except Exception as exc:
                for conn in (dst, src):
                    if conn is not None:
                        try:
                            conn.close()
                        except Exception:
                            pass
                if os.path.exists(tmp_file):
                    try:
                        os.remove(tmp_file)
                    except Exception:
                        pass
                self.stdout.write(self.style.ERROR(f"[ERROR] Zaxiralashda xatolik: {exc}"))
                return
        else:
            from django.core.management import call_command
            backup_file = os.path.join(backups_dir, f"smartlib_backup_{now_str}.json")
            tmp_file = f"{backup_file}.tmp"
            try:
                with open(tmp_file, 'w', encoding='utf-8') as out_f:
                    call_command('dumpdata', indent=2, stdout=out_f)
                os.replace(tmp_file, backup_file)
                self._write_sha256_manifest(backup_file)
                file_size_kb = round(os.path.getsize(backup_file) / 1024, 1)
                self.stdout.write(self.style.SUCCESS(f"[OK] Baza to'liq zaxiralandi (JSON): {backup_file} ({file_size_kb} KB)"))
            except Exception as exc:
                if os.path.exists(tmp_file):
                    try:
                        os.remove(tmp_file)
                    except Exception:
                        pass
                self.stdout.write(self.style.ERROR(f"[ERROR] Zaxiralashda xatolik: {exc}"))
                return

        # Rotatsiya: eng kamida MIN_BACKUPS_RETAINED (10 ta) eng yangi zaxirani har doim saqlab qolish (Zero Data Loss)
        cutoff = datetime.now() - timedelta(days=self.RETENTION_DAYS)
        backup_candidates = []
        for fname in os.listdir(backups_dir):
            if fname.startswith("smartlib_backup_") and (
                fname.endswith(".sqlite3") or fname.endswith(".json") or fname.endswith(".sql")
            ):
                fpath = os.path.join(backups_dir, fname)
                try:
                    mtime = os.path.getmtime(fpath)
                    backup_candidates.append((mtime, fpath))
                except Exception:
                    pass

        # Yangilaridan eskilariga qarab saralash
        backup_candidates.sort(key=lambda item: item[0], reverse=True)
        # Eng so'nggi 10 ta zaxiraga hech qachon tegilmaydi
        old_candidates = backup_candidates[self.MIN_BACKUPS_RETAINED:]
        for mtime_ts, fpath in old_candidates:
            try:
                if datetime.fromtimestamp(mtime_ts) < cutoff:
                    os.remove(fpath)
                    sha_companion = f"{fpath}.sha256"
                    if os.path.exists(sha_companion):
                        os.remove(sha_companion)
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
