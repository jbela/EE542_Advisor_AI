$ErrorActionPreference = "Stop"

# Automatically locate the project directory
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

# Use the active Python installation
$Python = (py -c "import sys; print(sys.executable)").Trim()

if ($LASTEXITCODE -ne 0 -or -not $Python) {
    throw "Python could not be found."
}

# Create logs directory
$LogDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Create a unique log file
$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$LogFile = Join-Path $LogDir "sync_$Timestamp.log"

# Write log header
"USC Advisor AI Sync - $(Get-Date)" |
    Out-File -FilePath $LogFile -Encoding utf8

# Run synchronization and capture output
try {
    & $Python -m ingestion.run_sync 2>&1 |
        Out-File -FilePath $LogFile -Append -Encoding utf8

    $ExitCode = $LASTEXITCODE

    if ($null -eq $ExitCode) {
        $ExitCode = 1
    }
}
catch {
    $_ | Out-File -FilePath $LogFile -Append -Encoding utf8
    $ExitCode = 1
}

# Record execution result
"Exit code: $ExitCode" |
    Out-File -FilePath $LogFile -Append -Encoding utf8

exit $ExitCode
