$projectRoot = Split-Path -Parent $PSScriptRoot
$s = New-Object -ComObject WScript.Shell
$lnk = $s.CreateShortcut(
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Universal Downloader Pro.lnk'))
$lnk.TargetPath = Join-Path $projectRoot 'launcher\universal-downloader-pro.bat'
$lnk.WorkingDirectory = $projectRoot
$lnk.Save()
Write-Output "Shortcut updated to bat launcher"
