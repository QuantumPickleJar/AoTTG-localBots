param(
    [string]$PythonExe,
    [switch]$KeepArtifacts
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$smokeProject = Join-Path $PSScriptRoot 'FlightRecorder.TransportClient.Smoke\FlightRecorder.TransportClient.Smoke.csproj'
if (-not $PythonExe) {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python executable not found: $PythonExe"
}

$caseId = [guid]::NewGuid().ToString('N')
$pipeName = "aicadets-it-$caseId"
$runId = [guid]::NewGuid().ToString('N')
$root = Join-Path ([IO.Path]::GetTempPath()) "aicadets-flight-transport-$caseId"
$outputDir = Join-Path $root 'recordings'
$configPath = Join-Path $root 'receiver.json'
$stdoutPath = Join-Path $root 'receiver.stdout.log'
$stderrPath = Join-Path $root 'receiver.stderr.log'
$reportDir = Join-Path $root 'analysis'
$null = New-Item -ItemType Directory -Path $root -Force

$config = @{
    recording_enabled = $true
    pipe_name = $pipeName
    output_dir = $outputDir
    writer_limits = @{
        max_storage_bytes = 4194304
        chunk_target_bytes = 65536
        max_chunks = 8
    }
} | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText($configPath, $config, [Text.UTF8Encoding]::new($false))

$receiverScript = Join-Path $repoRoot 'tools\flight_transport.py'
$receiverArguments = '"{0}" --config "{1}"' -f $receiverScript, $configPath
$receiver = Start-Process -FilePath $PythonExe `
    -ArgumentList $receiverArguments `
    -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
try {
    $readyDeadline = [DateTime]::UtcNow.AddSeconds(15)
    while ([DateTime]::UtcNow -lt $readyDeadline) {
        if ($receiver.HasExited) {
            $errorText = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { '' }
            throw "Receiver exited during startup (code $($receiver.ExitCode)): $errorText"
        }
        if ((Test-Path -LiteralPath $stdoutPath) -and
            (Get-Content -LiteralPath $stdoutPath -Raw) -match 'listening on local pipe') { break }
        Start-Sleep -Milliseconds 100
    }
    if (-not (Test-Path -LiteralPath $stdoutPath) -or
        (Get-Content -LiteralPath $stdoutPath -Raw) -notmatch 'listening on local pipe') {
        throw 'Receiver did not report that its local pipe is listening.'
    }

    dotnet run --project $smokeProject --configuration Release -- --send-to-python $pipeName $runId
    if ($LASTEXITCODE -ne 0) { throw "Transport producer exited with code $LASTEXITCODE" }
    if (-not $receiver.WaitForExit(15000)) { throw 'Receiver did not stop after the producer stop message.' }
    $receiver.Refresh()
    if ($null -ne $receiver.ExitCode -and [int]$receiver.ExitCode -ne 0) {
        $errorText = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { '' }
        throw "Receiver exited with code $($receiver.ExitCode): $errorText"
    }

    $runDir = Join-Path $outputDir "run-$runId"
    $metadata = Get-Content -LiteralPath (Join-Path $runDir 'metadata.json') -Raw | ConvertFrom-Json
    if ($metadata.schema_version -ne 'aicadets.flight.v1' -or
        $metadata.capture_tier -ne 'transport_only' -or -not $metadata.capture_complete) {
        throw 'Writer output has the wrong schema or is unexpectedly incomplete.'
    }
    $manifest = Get-Content -LiteralPath (Join-Path $runDir 'chunk_manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.chunks.Count -lt 1) { throw 'Writer produced no hashed chunks.' }
    & $PythonExe (Join-Path $repoRoot 'tools\analyze_flight.py') $runDir --out $reportDir
    if ($LASTEXITCODE -ne 0) { throw "Flight analyzer exited with code $LASTEXITCODE" }
    Write-Output "Windows pipe-to-writer smoke passed. Run: $runDir"
}
finally {
    if (-not $receiver.HasExited) {
        Stop-Process -Id $receiver.Id -Force -ErrorAction SilentlyContinue
    }
    if (-not $KeepArtifacts -and (Test-Path -LiteralPath $root)) {
        $resolvedRoot = (Resolve-Path -LiteralPath $root).Path
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if ($resolvedRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and
            $resolvedRoot -like '*aicadets-flight-transport-*') {
            Remove-Item -LiteralPath $resolvedRoot -Recurse -Force
        } else {
            throw "Refusing to remove test output outside its temp folder: $resolvedRoot"
        }
    }
}
