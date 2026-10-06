$s = New-Object -ComObject WScript.Shell
$lnk = $s.CreateShortcut("$env:USERPROFILE\Desktop\Universal Downloader Pro.lnk")
$lnk.TargetPath = "C:\Users\user\Projects\universal-downloader-pro\launcher\universal-downloader-pro.bat"
$lnk.WorkingDirectory = "C:\Users\user\Projects\universal-downloader-pro"
$lnk.Save()
Write-Output "Shortcut updated to bat launcher"
