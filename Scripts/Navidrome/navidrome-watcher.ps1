# Clean Navidrome Auto-Watcher (Safe Version)

# Load environment variables from .env file
$envContent = Get-Content "$PSScriptRoot\..\.env" | Where-Object { $_ -notmatch '^#' } | ConvertFrom-StringData

$folder = $envContent.MUSIC_DIR
$dockerContainer = "navidrome"
$minInterval = 300   # 5 minutes between rescans
$lockFile = $envContent.NAVIDROME_DIR + "\navidrome-scan.lock"
$global:lastScan = (Get-Date).AddSeconds(-10)

# Check if Navidrome container is running
function Test-Navidrome {
    $running = docker ps --filter "name=$dockerContainer" --format '{{.Names}}'
    return $running -match $dockerContainer
}

# Trigger a rescan safely
function RescanNavidrome {
    if (Test-Navidrome) {
        # Check for lock file to prevent overlapping scans
        if (Test-Path $lockFile) {
            Write-Host "Scan lock file exists, skipping..."
            return
        }

        try {
            # Create lock file
            New-Item -ItemType File -Path $lockFile -Force | Out-Null
            Write-Host "Rescanning Navidrome..."
            docker exec $dockerContainer /app/navidrome scan 2>&1 | ForEach-Object { Write-Host $_ }
        } catch {
            Write-Host "Error during scan: $($_.Exception.Message)"
        } finally {
            # Remove lock file
            if (Test-Path $lockFile) {
                Remove-Item $lockFile -Force
            }
        }
    } else {
        Write-Host "Container not running - skipping scan."
    }
}

# Create the folder watcher
$watcher = New-Object System.IO.FileSystemWatcher -ArgumentList $folder, "*.*"
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true

# Action to take when a change is detected
$action = {
    Start-Sleep -Seconds 10  # debounce for duplicate events

    $path = $event.SourceEventArgs.FullPath
    $type = $event.SourceEventArgs.ChangeType
    Write-Host "Event: $type at $path"

    $now = Get-Date
    if (($now - $global:lastScan).TotalSeconds -ge $minInterval) {
        $global:lastScan = $now
        Write-Host "Triggering Navidrome rescan..."
        RescanNavidrome
    } else {
        Write-Host "Cooldown active, skipping scan."
    }
}

# Register events
Register-ObjectEvent $watcher Changed -Action $action | Out-Null
Register-ObjectEvent $watcher Created -Action $action | Out-Null
Register-ObjectEvent $watcher Deleted -Action $action | Out-Null
Register-ObjectEvent $watcher Renamed -Action $action | Out-Null

Write-Host "Watching folder: $folder"

# Keep script running
while ($true) {
    Start-Sleep 5
}
