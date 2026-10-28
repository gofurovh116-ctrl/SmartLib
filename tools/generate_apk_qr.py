import qrcode
import os

url = "https://smartlib-1-olyc.onrender.com/download/apk/"
qr = qrcode.QRCode(box_size=10, border=2)
qr.add_data(url)
qr.make(fit=True)
img = qr.make_image(fill_color="#1e293b", back_color="#ffffff")

out_dir = r"C:\Users\xgofu\.gemini\antigravity\brain\910dc138-b15a-4269-9176-dca15cfcf09a"
out_path = os.path.join(out_dir, "qr_download_apk.png")
img.save(out_path)
print(f"QR saved to {out_path}")

# Also save to static and media
static_qr = r"D:\SmartLib\static\img\qr_download_apk.png"
os.makedirs(os.path.dirname(static_qr), exist_ok=True)
img.save(static_qr)
print(f"QR saved to {static_qr}")

