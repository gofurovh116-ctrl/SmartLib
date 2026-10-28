import os
from PIL import Image, ImageDraw, ImageFont

def create_smartlib_icon():
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background rounded rectangle
    # Royal blue #2563eb
    bg_color = (37, 99, 235, 255)
    corner_radius = 110
    
    # Draw rounded rect
    draw.rounded_rectangle([16, 16, size - 16, size - 16], radius=corner_radius, fill=bg_color)

    # Subtle inner border / glow
    draw.rounded_rectangle([20, 20, size - 20, size - 20], radius=corner_radius - 4, outline=(96, 165, 250, 180), width=6)

    # Draw stylish open book in white
    # Book spine center at x=256
    cx = 256
    top_y = 130
    mid_y = 300
    bottom_y = 320
    
    # Left page
    left_page = [
        (cx - 10, top_y + 30),
        (cx - 140, top_y + 10),
        (cx - 170, top_y + 20),
        (cx - 170, bottom_y - 20),
        (cx - 140, bottom_y - 30),
        (cx - 10, mid_y),
    ]
    draw.polygon(left_page, fill=(255, 255, 255, 255))

    # Right page
    right_page = [
        (cx + 10, top_y + 30),
        (cx + 140, top_y + 10),
        (cx + 170, top_y + 20),
        (cx + 170, bottom_y - 20),
        (cx + 140, bottom_y - 30),
        (cx + 10, mid_y),
    ]
    draw.polygon(right_page, fill=(240, 246, 255, 255))

    # Golden bookmark ribbon
    bookmark = [
        (cx - 16, top_y + 10),
        (cx + 16, top_y + 10),
        (cx + 16, bottom_y + 30),
        (cx, bottom_y + 10),
        (cx - 16, bottom_y + 30),
    ]
    draw.polygon(bookmark, fill=(245, 158, 11, 255)) # amber-500

    # Draw page lines
    for offset in [-40, -80, -120]:
        draw.line([(cx + offset, top_y + 70), (cx + offset, bottom_y - 60)], fill=(203, 213, 225, 200), width=4)
    for offset in [40, 80, 120]:
        draw.line([(cx + offset, top_y + 70), (cx + offset, bottom_y - 60)], fill=(203, 213, 225, 200), width=4)

    # Center spine line
    draw.line([(cx, top_y + 25), (cx, mid_y + 5)], fill=(30, 58, 138, 255), width=8)

    # QR scan line effect over book
    draw.line([(cx - 150, top_y + 110), (cx + 150, top_y + 110)], fill=(52, 211, 153, 230), width=6) # emerald beam

    # Text at the bottom: SMARTLIB
    # Since default font might not have truetype, draw clean bold letters or fallback
    try:
        font = ImageFont.truetype("arialbd.ttf", 46)
        draw.text((cx, 410), "SMARTLIB", font=font, fill=(255, 255, 255, 255), anchor="mm")
    except Exception:
        draw.text((cx - 80, 390), "SMARTLIB", fill=(255, 255, 255, 255))

    os.makedirs("D:/SmartLib/dist", exist_ok=True)
    os.makedirs("D:/SmartLib/media/app", exist_ok=True)
    
    png_path = "D:/SmartLib/dist/smartlib_icon.png"
    ico_path = "D:/SmartLib/dist/smartlib_icon.ico"
    web_icon = "D:/SmartLib/media/app/icon-512.png"

    img.save(png_path, "PNG")
    img.save(web_icon, "PNG")

    # Save ICO with multiple sizes for Windows
    img.save(ico_path, format="ICO", sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
    print(f"Generated icons: {png_path}, {ico_path}, {web_icon}")

if __name__ == "__main__":
    create_smartlib_icon()
