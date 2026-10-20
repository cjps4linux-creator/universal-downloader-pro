$projectRoot = Split-Path -Parent $PSScriptRoot
$s = (New-Object -ComObject WScript.Shell).CreateShortcut(
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Universal Downloader Pro.lnk'))
$s.TargetPath = Join-Path $projectRoot 'launcher\start-venv.cmd'
$s.WorkingDirectory = $projectRoot
$s.Save()
