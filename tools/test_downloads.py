import urllib.request

def test_downloads():
    urls = [
        "http://127.0.0.1:8000/download/apk/",
        "http://127.0.0.1:8000/download/pc/",
        "http://127.0.0.1:8000/media/SmartLib.apk",
        "http://127.0.0.1:8000/media/SmartLib_Desktop.exe",
    ]
    for u in urls:
        try:
            req = urllib.request.Request(u, method="HEAD")
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"[OK] {u} -> Status: {resp.status}, Type: {resp.headers.get('Content-Type')}, Length: {resp.headers.get('Content-Length')}")
        except Exception as e:
            print(f"[ERR] {u} -> {e}")

if __name__ == "__main__":
    test_downloads()
