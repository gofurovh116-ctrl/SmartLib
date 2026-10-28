"""
SmartLib Global HTTPS Tunnel Daemon (Cloudflare HTTP/2 + IPv4 Edge Tunnel).
Uzbekiston provayderlarida bloklanmaydigan --protocol http2 --edge-ip-version 4 rejimi bilan
doimiy (hech qachon 3 daqiqada almashib qolmaydigan va 502 bermaydigan) https://*.trycloudflare.com
manzilini oladi va backups/public_url.txt fayliga yozadi.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / 'backups'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
PUBLIC_URL_FILE = BACKUP_DIR / 'public_url.txt'
CLOUDFLARED_BIN = Path(__file__).resolve().parent / 'cloudflared.exe'

CF_URL_REGEX = re.compile(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)')


def run_tunnel():
    cmd = [
        str(CLOUDFLARED_BIN),
        'tunnel',
        '--url', 'http://127.0.0.1:8000',
        '--protocol', 'http2',
        '--edge-ip-version', '4',
        '--no-autoupdate',
    ]

    while True:
        print("[SmartLib Tunnel] Cloudflare Global HTTPS (HTTP/2 + IPv4) ulanmoqda...", flush=True)
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                m = CF_URL_REGEX.search(line)
                if m:
                    pub_url = m.group(1).strip()
                    if 'api.trycloudflare.com' in pub_url:
                        continue
                    PUBLIC_URL_FILE.write_text(pub_url, encoding='utf-8')
                    print(f"\n=======================================================", flush=True)
                    print(f"  SMARTLIB GLOBAL ONLINE URL: {pub_url}", flush=True)
                    print(f"=======================================================\n", flush=True)
            proc.wait()
        except Exception as exc:
            print(f"[SmartLib Tunnel] Xatolik: {exc}", flush=True)
        time.sleep(3)


if __name__ == '__main__':
    run_tunnel()
