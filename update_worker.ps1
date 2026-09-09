param([Parameter(Mandatory=$true)][string]$Job)
$ErrorActionPreference = 'Stop'
$jobData = Get-Content -LiteralPath $Job -Raw | ConvertFrom-Json
$root = [IO.Path]::GetFullPath($jobData.target)
$work = [IO.Path]::GetFullPath($jobData.work)
$journal = Join-Path $work 'transaction.json'
$health = Join-Path $work 'healthy.json'
$pending = Join-Path $work 'prepared-update.json'
$backup = Join-Path $work 'backup'
$stage = Join-Path $work 'stage'
$entries = @()
$child = $null
function SafePath($base, $relative) {
    $path = [IO.Path]::GetFullPath((Join-Path $base $relative))
    if (-not $path.StartsWith($base.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe path' }
    $check = $path
    while ($check -and $check.Length -ge $base.Length) {
        if ((Test-Path -LiteralPath $check) -and ((Get-Item -LiteralPath $check -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Reparse point in update path' }
        $check = Split-Path $check
    }
    return $path
}
function SaveJournal($status) {
    @{status=$status; entries=@($script:entries); version=$jobData.version; revision=$jobData.revision} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "$journal.tmp" -Encoding UTF8
    Move-Item -LiteralPath "$journal.tmp" -Destination $journal -Force
}
function RestoreFiles {
    foreach ($entry in $script:entries) {
        $dest = SafePath $root $entry.name
        if ($entry.existed) {
            $saved = SafePath $backup $entry.name
            if (-not (Test-Path -LiteralPath $dest) -or (Get-FileHash -LiteralPath $dest).Hash -ne (Get-FileHash -LiteralPath $saved).Hash) {
                Copy-Item -LiteralPath $saved -Destination $dest -Force
            }
        }
        elseif (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Force }
    }
}
$mutex = New-Object Threading.Mutex($false, 'Local\SIGA-Apply')
if (-not $mutex.WaitOne(0)) { exit 2 }
try {
    $parentProcess = Get-Process -Id $jobData.parent -ErrorAction SilentlyContinue
    if ($parentProcess -and -not $parentProcess.WaitForExit(120000)) { throw 'SIGA did not close' }
    if (Test-Path -LiteralPath $journal) {
        $previous = Get-Content -LiteralPath $journal -Raw | ConvertFrom-Json
        if ($previous.status -eq 'applying') {
            $entries = @($previous.entries)
            RestoreFiles
            SaveJournal 'rolled-back'
            Remove-Item -LiteralPath $pending -Force -ErrorAction SilentlyContinue
            Start-Process -FilePath (Join-Path $root 'SIGA.exe') -WorkingDirectory $root -WindowStyle Hidden
            exit 0
        }
    }
    if ((Get-FileHash -LiteralPath $jobData.source -Algorithm SHA256).Hash -ne $jobData.sha256) { throw 'SHA256 mismatch' }
    # Only application files are accepted; user folders never enter the transaction.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($jobData.source)
    try {
        $seen = @{}
        foreach ($item in $zip.Entries) {
            $name = $item.FullName.Replace('/', '\')
            if ($name.EndsWith('\')) { continue }
            if ($name -ne 'SIGA.exe' -and $name -ne 'siga-desktop-icon.ico' -and -not $name.StartsWith('_internal\')) { throw 'Non-application file in package' }
            if ($name.Contains(':') -or $seen.ContainsKey($name)) { throw 'Invalid package path' }
            $seen[$name] = $true
            $dest = SafePath $stage $name
            New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($item, $dest, $true)
        }
    } finally { $zip.Dispose() }
    $entries = @()
    foreach ($name in $seen.Keys) {
        $dest = SafePath $root $name
        $exists = Test-Path -LiteralPath $dest
        if ($exists) {
            $saved = SafePath $backup $name
            New-Item -ItemType Directory -Path (Split-Path $saved) -Force | Out-Null
            Copy-Item -LiteralPath $dest -Destination $saved -Force
        }
        $entries += @{name=$name; existed=$exists}
    }
    SaveJournal 'applying'
    foreach ($entry in $entries) {
        $dest = SafePath $root $entry.name
        New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
        Copy-Item -LiteralPath (SafePath $stage $entry.name) -Destination $dest -Force
    }
    # Clear the pending request BEFORE launch, eliminating the restart loop.
    Remove-Item -LiteralPath $pending -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $health -Force -ErrorAction SilentlyContinue
    $env:SIGA_UPDATE_HEALTH = $health
    $child = Start-Process -FilePath (Join-Path $root 'SIGA.exe') -WorkingDirectory $root -WindowStyle Hidden -PassThru
    Remove-Item Env:SIGA_UPDATE_HEALTH
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    $healthy = $false
    while ([DateTime]::UtcNow -lt $deadline -and -not $child.HasExited) {
        if (Test-Path -LiteralPath $health) {
            $result = Get-Content -LiteralPath $health -Raw | ConvertFrom-Json
            if ($result.version -eq $jobData.version -and $result.revision -eq $jobData.revision) { $healthy = $true; break }
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $healthy) { throw 'Updated application did not confirm startup' }
    SaveJournal 'committed'
} catch {
    $_ | Out-String | Add-Content -LiteralPath (Join-Path $work 'worker-error.log')
    if ($child -and -not $child.HasExited) { Stop-Process -Id $child.Id -Force; $child.WaitForExit() }
    if (Test-Path -LiteralPath $journal) {
        $current = Get-Content -LiteralPath $journal -Raw | ConvertFrom-Json
        if ($current.status -eq 'applying') { $entries=@($current.entries); RestoreFiles; SaveJournal 'rolled-back' }
    }
    Remove-Item -LiteralPath $pending -Force -ErrorAction SilentlyContinue
    Remove-Item Env:SIGA_UPDATE_HEALTH -ErrorAction SilentlyContinue
    Start-Process -FilePath (Join-Path $root 'SIGA.exe') -WorkingDirectory $root -WindowStyle Hidden
    exit 1
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
