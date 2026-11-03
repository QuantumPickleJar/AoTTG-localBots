param(
    [Parameter(Mandatory = $true)]
    [string]$PackageRoot,
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,
    [string]$PythonExe
)

$ErrorActionPreference = "Stop"
$package = (Resolve-Path -LiteralPath $PackageRoot).Path
$config = (Resolve-Path -LiteralPath $ConfigPath).Path
$receiverScript = Join-Path $package "tools\flight_transport.py"
if (-not (Test-Path -LiteralPath $receiverScript -PathType Leaf)) {
    throw "Flight Recorder receiver script is missing: $receiverScript"
}

$receiverConfig = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
if ($receiverConfig.recording_enabled -ne $true) {
    throw "Set recording_enabled=true in the local receiver config before starting a capture."
}
if ([string]::IsNullOrWhiteSpace([string]$receiverConfig.pipe_name) -or
    [string]::IsNullOrWhiteSpace([string]$receiverConfig.output_dir)) {
    throw "Receiver config must specify pipe_name and output_dir."
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = Join-Path $package "runtime\python.exe"
}
$python = (Resolve-Path -LiteralPath $PythonExe).Path

$logDirectory = Join-Path (Split-Path -Parent $config) "logs"
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$stamp = [DateTime]::Now.ToString("yyyyMMdd-HHmmss")
$stdout = Join-Path $logDirectory "flight-recorder-$stamp.stdout.log"
$stderr = Join-Path $logDirectory "flight-recorder-$stamp.stderr.log"
$arguments = '"{0}" --config "{1}"' -f $receiverScript, $config
$process = Start-Process -FilePath $python -ArgumentList $arguments -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr

try {
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    while ([DateTime]::UtcNow -lt $deadline) {
        $process.Refresh()
        if ($process.HasExited) {
            $errorText = if (Test-Path -LiteralPath $stderr) { Get-Content -LiteralPath $stderr -Raw } else { "" }
            throw "Flight Recorder receiver exited during startup (code $($process.ExitCode)): $errorText"
        }
        if ((Test-Path -LiteralPath $stdout) -and
            (Get-Content -LiteralPath $stdout -Raw) -match "listening on local pipe") { break }
        Start-Sleep -Milliseconds 100
    }
    if (-not (Test-Path -LiteralPath $stdout) -or
        (Get-Content -LiteralPath $stdout -Raw) -notmatch "listening on local pipe") {
        throw "Flight Recorder receiver did not become ready within 20 seconds. See $stderr"
    }
}
catch {
    $process.Refresh()
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    throw
}

Write-Output "Receiver is listening on the configured local pipe."
Write-Output "PID: $($process.Id)"
Write-Output "Pipe: $($receiverConfig.pipe_name)"
Write-Output "Stdout: $stdout"
Write-Output "Stderr: $stderr"
