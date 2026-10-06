$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:USERPROFILE\Desktop\Universal Downloader Pro.lnk")
$s.TargetPath = "C:\Users\user\Projects\universal-downloader-pro\launcher\start-venv.cmd"
$s.WorkingDirectory = "C:\Users\user\Projects\universal-downloader-pro"
$s.Save()
