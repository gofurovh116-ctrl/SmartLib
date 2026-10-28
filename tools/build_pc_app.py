import os
import sys
import subprocess

CSC_PATH = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
CS_SOURCE = r"D:\SmartLib\tools\SmartLibApp.cs"
OUT_EXE = r"D:\SmartLib\dist\SmartLib_Desktop.exe"
ICON_PATH = r"D:\SmartLib\dist\smartlib_icon.ico"
MEDIA_DIR = r"D:\SmartLib\media"

def compile_pc_app():
    print("[*] Compiling SmartLib Windows PC Desktop Application...")
    if not os.path.exists(CSC_PATH):
        raise FileNotFoundError(f"C# compiler not found at {CSC_PATH}")
    
    os.makedirs(r"D:\SmartLib\dist", exist_ok=True)
    os.makedirs(MEDIA_DIR, exist_ok=True)

    cmd = [
        CSC_PATH,
        "/nologo",
        "/target:winexe",
        f"/out:{OUT_EXE}",
        f"/win32icon:{ICON_PATH}",
        "/reference:System.Windows.Forms.dll,System.Drawing.dll,System.dll",
        "/optimize+",
        CS_SOURCE
    ]

    print("[*] Executing:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("[!] Compilation failed:\n", res.stderr or res.stdout, file=sys.stderr)
        sys.exit(res.returncode)

    print(f"[+] PC Executable successfully compiled: {OUT_EXE}")
    size_kb = os.path.getsize(OUT_EXE) / 1024
    print(f"[+] File size: {size_kb:.2f} KB")

    # Also copy to media for direct download from browser if needed
    dest_media = os.path.join(MEDIA_DIR, "SmartLib_Desktop.exe")
    with open(OUT_EXE, "rb") as fsrc, open(dest_media, "wb") as fdst:
        fdst.write(fsrc.read())
    print(f"[+] Downloadable copy placed at: {dest_media}")

    # Create Desktop shortcut for the user if Desktop exists
    desktop_path = os.path.expanduser("~/Desktop")
    if os.path.exists(desktop_path):
        try:
            # Create a PowerShell script or VBS script to make .lnk
            vbs_script = f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{desktop_path}\\SmartLib.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{OUT_EXE}"
oLink.WorkingDirectory = "D:\\SmartLib"
oLink.Description = "SmartLib Kutubxona Tizimi"
oLink.IconLocation = "{ICON_PATH}, 0"
oLink.Save
"""
            vbs_file = r"D:\SmartLib\dist\make_shortcut.vbs"
            with open(vbs_file, "w", encoding="utf-8") as f:
                f.write(vbs_script)
            subprocess.run(["cscript", "//nologo", vbs_file], check=True)
            print(f"[+] Desktop shortcut created at: {desktop_path}\\SmartLib.lnk")
        except Exception as e:
            print(f"[!] Note: Could not create desktop shortcut automatically: {e}")

if __name__ == "__main__":
    compile_pc_app()
