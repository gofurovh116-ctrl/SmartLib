import hashlib
import os
import shutil
import sqlite3
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connections


class Command(BaseCommand):
    help = (
        "SmartLib ma'lumotlar bazasini zaxira nusxasidan xavfsiz tiklash (Zero Data Loss): "
        "SHA-256 va PRAGMA integrity_check tekshiruvi, tiklashdan oldingi zaxira (pre-restore snapshot) "
        "hamda SQLite WAL/SHM qoldiqlarini xavfsiz tozalash bilan."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='',
            help="Tiklanishi kerak bo'lgan zaxira (.sqlite3) fayl yo'li",
        )
        parser.add_argument(
            '--latest',
            action='store_true',
            help="backups/database papkasidagi eng so'nggi yaroqli zaxirani tiklash",
        )
        parser.add_argument(
            '--target',
            type=str,
            default='',
            help="Ixtiyoriy: tiklanadigan maqsadli baza fayli yo'li (default: settings.DATABASES['default']['NAME'])",
        )

    @staticmethod
    def _compute_sha256(file_path):
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def _verify_sha256_if_present(cls, backup_path):
        sha_path = f"{backup_path}.sha256"
        if not os.path.isfile(sha_path):
            return True, "SHA-256 manifest fayli mavjud emas (o'tkazib yuborildi)"
        with open(sha_path, 'r', encoding='utf-8') as sf:
            content = sf.read().strip()
        if not content:
            raise CommandError(f"SHA-256 manifest fayli bo'sh: {sha_path}")
        expected_hash = content.split()[0].strip().lower()
        actual_hash = cls._compute_sha256(backup_path).lower()
        if expected_hash != actual_hash:
            raise CommandError(
                f"SHA-256 nazorat summasi mos kelmadi! Kutilgan: {expected_hash}, Haqiqiy: {actual_hash}"
            )
        return True, actual_hash

    @staticmethod
    def _verify_sqlite_integrity(sqlite_path):
        conn = None
        try:
            conn = sqlite3.connect(sqlite_path)
            row = conn.execute("PRAGMA integrity_check;").fetchone()
            status = row[0] if row else "failed"
            if str(status).lower() != "ok":
                raise CommandError(f"SQLite PRAGMA integrity_check xatosi ({sqlite_path}): {status}")
            # Jadval mavjudligini ham tekshirish (bo'sh 0-jadval fayl ustiga yozilmasligi uchun)
            tables = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table';").fetchone()[0]
            if tables == 0:
                raise CommandError(f"Zaxira faylida jadvallar topilmadi (bo'sh baza): {sqlite_path}")
        except sqlite3.Error as exc:
            raise CommandError(f"Yaroqsiz SQLite fayli ({sqlite_path}): {exc}") from exc
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _find_latest_backup(self, backups_dir):
        if not os.path.isdir(backups_dir):
            raise CommandError(f"Zaxira papkasi topilmadi: {backups_dir}")
        candidates = []
        for fname in os.listdir(backups_dir):
            if fname.startswith("smartlib_backup_") and fname.endswith(".sqlite3"):
                fpath = os.path.join(backups_dir, fname)
                if os.path.isfile(fpath) and os.path.getsize(fpath) > 0:
                    candidates.append((os.path.getmtime(fpath), fpath))
        if not candidates:
            raise CommandError(f"Hech qanday .sqlite3 zaxira fayli topilmadi: {backups_dir}")
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def handle(self, *args, **options):
        base_dir = str(settings.BASE_DIR)
        backups_dir = os.path.join(base_dir, 'backups', 'database')
        os.makedirs(backups_dir, exist_ok=True)

        file_arg = (options.get('file') or '').strip()
        use_latest = bool(options.get('latest'))
        target_arg = (options.get('target') or '').strip()

        if not file_arg and not use_latest:
            raise CommandError("Iltimos, --file <zaxira_yoli> yoki --latest parametrini ko'rsating.")

        if file_arg:
            backup_path = os.path.abspath(file_arg)
        else:
            backup_path = self._find_latest_backup(backups_dir)

        if not os.path.isfile(backup_path):
            raise CommandError(f"Zaxira fayli topilmadi: {backup_path}")
        if os.path.getsize(backup_path) == 0:
            raise CommandError(f"Zaxira fayli bo'sh (0 bayt): {backup_path}")

        # 1. SHA-256 tekshiruvi
        _, sha_info = self._verify_sha256_if_present(backup_path)
        self.stdout.write(f"[OK] SHA-256 tekshiruvi: {sha_info}")

        # 2. SQLite PRAGMA integrity_check tekshiruvi
        self._verify_sqlite_integrity(backup_path)
        self.stdout.write(f"[OK] SQLite PRAGMA integrity_check tasdiqlandi: {backup_path}")

        target_db = os.path.abspath(target_arg) if target_arg else os.path.abspath(str(settings.DATABASES['default']['NAME']))

        # 3. Faol ulanishlarni yopish
        connections.close_all()

        # 4. Zero Data Loss: Tiklashdan oldin joriy bazaning xavfsizlik nusxasini (pre-restore snapshot) olish
        now_str = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        if os.path.isfile(target_db) and os.path.getsize(target_db) > 0:
            prerestore_path = os.path.join(backups_dir, f"db.sqlite3.prerestore_{now_str}")
            try:
                src = sqlite3.connect(target_db)
                dst = sqlite3.connect(prerestore_path)
                src.backup(dst)
                dst.close()
                src.close()
            except Exception:
                shutil.copy2(target_db, prerestore_path)
            self.stdout.write(self.style.WARNING(f"[SAFEGUARD] Joriy baza tiklashdan oldin saqlandi: {prerestore_path}"))

        # 5. Vaqtinchalik faylga nusxalab, tekshirib, WAL/SHM qoldiqlarini tozalash va atomik almashtirish
        stage_tmp = f"{target_db}.restore_tmp_{now_str}"
        try:
            shutil.copy2(backup_path, stage_tmp)
            self._verify_sqlite_integrity(stage_tmp)

            # SQLite WAL va SHM qoldiqlarini tozalash (eski jurnal yangi tiklangan bazani buzmasligi uchun)
            for suffix in ('-wal', '-shm'):
                sidecar = f"{target_db}{suffix}"
                if os.path.exists(sidecar):
                    try:
                        os.remove(sidecar)
                    except OSError:
                        # Agar fayl band bo'lsa, nomini o'zgartirib chetga olish
                        os.replace(sidecar, f"{sidecar}.old_{now_str}")

            os.replace(stage_tmp, target_db)
            self.stdout.write(self.style.SUCCESS(f"[OK] Ma'lumotlar bazasi muvaffaqiyatli tiklandi: {target_db}"))
        finally:
            if os.path.exists(stage_tmp):
                try:
                    os.remove(stage_tmp)
                except Exception:
                    pass
