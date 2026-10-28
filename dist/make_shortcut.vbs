
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "C:\Users\xgofu/Desktop\SmartLib.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "D:\SmartLib\dist\SmartLib_Desktop.exe"
oLink.WorkingDirectory = "D:\SmartLib"
oLink.Description = "SmartLib Kutubxona Tizimi"
oLink.IconLocation = "D:\SmartLib\dist\smartlib_icon.ico, 0"
oLink.Save
