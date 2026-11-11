param([ValidateSet('Local','Public','Links')][string]$Target = 'Links')
$ErrorActionPreference = 'Stop'
if ((Get-ScheduledTask -TaskName 'Punca-Runtime').State -ne 'Running') {
    Start-ScheduledTask -TaskName 'Punca-Runtime'
}
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $status = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/status.json' -TimeoutSec 2
        if ($Target -ne 'Public' -or $status.publicUrl) { break }
    } catch {}
    Start-Sleep -Seconds 2
}
$destination = switch ($Target) {
    'Local' { 'http://localhost:5173' }
    'Public' { 'http://localhost:8766/public' }
    default { 'http://localhost:8766/' }
}
# Invoked by the user from the Start menu: show their browser intentionally.
Start-Process $destination
