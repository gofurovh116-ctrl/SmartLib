"""
SmartLib - Xavfsiz (WAL-mos) SQLite zaxira nusxa olish skripti.

Oddiy fayl nusxalash WAL rejimida (-wal faylidagi) yozilmagan sahifalarni
yo'qotishi mumkin. Shuning uchun sqlite3 Online Backup API ishlatiladi.
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC = BASE_DIR / 'db.sqlite3'
BACKUP_DIR = BASE_DIR / 'backups'


def main():
    if not SRC.exists():
        print(f"[XATO] Baza topilmadi: {SRC}")
        return 1
    BACKUP_DIR.mkdir(exist_ok=True)
    dst_path = BACKUP_DIR / f"db_safe_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"

    src = sqlite3.connect(str(SRC))
    dst = sqlite3.connect(str(dst_path))
    try:
        src.backup(dst)
        integrity = dst.execute('PRAGMA integrity_check').fetchone()[0]
        print(f"[OK] Zaxira: {dst_path.name} | integrity_check = {integrity}")
        tables = [r[0] for r in dst.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        for t in tables:
            if t.startswith(('users_', 'books_')):
                cnt = dst.execute(f'SELECT COUNT(1) FROM "{t}"').fetchone()[0]
                print(f"    {t:<35} {cnt}")
        if integrity != 'ok':
            return 2
    finally:
        dst.close()
        src.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
