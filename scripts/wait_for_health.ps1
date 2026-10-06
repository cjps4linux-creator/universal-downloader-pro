$health = $args[0]
if (-not $health) { $health = 'http://127.0.0.1:8765/health' }
while ($true) {
  Start-Sleep -Seconds 1
  try {
    $r = Invoke-WebRequest -Uri $health -UseBasicParsing
    if ($r.StatusCode -eq 200) { exit 0 }
  } catch { }
}