$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:USERPROFILE\Desktop\Universal Downloader Pro.lnk")
Write-Output "TargetPath: $($s.TargetPath)"
Write-Output "WorkingDirectory: $($s.WorkingDirectory)"
