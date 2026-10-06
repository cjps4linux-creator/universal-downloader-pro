$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('C:\Users\user\Desktop\Universal Downloader Pro.lnk')
$s.TargetPath = 'C:\Users\user\Projects\universal-downloader-pro\launcher\universal-downloader-pro.bat'
$s.Arguments = ''
$s.WorkingDirectory = 'C:\Users\user\Projects\universal-downloader-pro'
$s.Save()
Write-Host 'Shortcut reset to bat launcher'
