$ws = New-Object -ComObject WScript.Shell
$projectRoot = Split-Path -Parent $PSScriptRoot
$s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Universal Downloader Pro.lnk')
$s.TargetPath = Join-Path $projectRoot 'launcher\universal-downloader-pro.bat'
$s.Arguments = ''
$s.WorkingDirectory = $projectRoot
$s.Save()
Write-Host 'Shortcut reset to bat launcher'
