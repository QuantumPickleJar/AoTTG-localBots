param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [Parameter(Mandatory = $true)]
    [string]$PythonEmbedDirectory
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $GameRoot).Path
$out = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $out -Force | Out-Null
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$sourceCommit = (& git -C $repo rev-parse HEAD 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $sourceCommit) { throw "Could not identify the package source commit." }
$sourceCommit = $sourceCommit.Trim()
$sourceChanges = @(& git -C $repo status --porcelain 2>$null)
if ($LASTEXITCODE -ne 0 -or $sourceChanges.Count -gt 0) {
    throw "Build the package from a clean, committed source tree so its manifest identifies the exact source."
}
$pythonSource = (Resolve-Path -LiteralPath $PythonEmbedDirectory).Path
$pythonExe = Join-Path $pythonSource "python.exe"
$pythonPth = Join-Path $pythonSource "python314._pth"
if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf) -or -not (Test-Path -LiteralPath $pythonPth -PathType Leaf)) {
    throw "Python 3.14.10 x64 embeddable runtime is incomplete: $pythonSource"
}
$pythonVersion = (& $pythonExe --version 2>&1) -join " "
if ($pythonVersion -notmatch '^Python 3\.14\.10$') { throw "Expected Python 3.14.10 x64 embeddable runtime; found: $pythonVersion" }
& (Join-Path $PSScriptRoot "build_flight_recorder_plugin.ps1") -GameRoot $root -Configuration Release
if ($LASTEXITCODE -ne 0) { throw "Plugin build script failed." }

$package = Join-Path $out "AoTTG2-FlightRecorder-0.1.8"
$zipPath = Join-Path $out "AoTTG2-FlightRecorder-0.1.8.zip"
if ((Test-Path -LiteralPath $package) -or (Test-Path -LiteralPath $zipPath)) {
    throw "Package output already exists. Choose a new OutputDirectory; no existing artifact was changed."
}

New-Item -ItemType Directory -Path $package | Out-Null
foreach ($directory in @("plugin", "tools", "scripts", "configs", "runtime", "docs")) {
    New-Item -ItemType Directory -Path (Join-Path $package $directory) | Out-Null
}

$pluginOutput = Join-Path $repo "plugin\FlightRecorder.UnityIl2Cpp\bin\Release\net6.0"
Copy-Item -LiteralPath (Join-Path $pluginOutput "AoTTG2.FlightRecorder.dll") -Destination (Join-Path $package "plugin")
Copy-Item -LiteralPath (Join-Path $pluginOutput "FlightRecorder.TransportClient.dll") -Destination (Join-Path $package "plugin")
foreach ($name in @("flight_transport.py", "flight_writer.py", "flight_attribution.py", "analyze_flight.py")) {
    Copy-Item -LiteralPath (Join-Path $repo "tools\$name") -Destination (Join-Path $package "tools")
}
Copy-Item -LiteralPath (Join-Path $repo "configs\flight-recorder-transport.example.json") -Destination (Join-Path $package "configs")
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "install_flight_recorder.ps1") -Destination (Join-Path $package "scripts")
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "remove_flight_recorder.ps1") -Destination (Join-Path $package "scripts")
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "start_flight_recorder_receiver.ps1") -Destination (Join-Path $package "scripts")
Copy-Item -LiteralPath (Join-Path $repo "docs\FLIGHT_RECORDER_IL2CPP_PACKAGE_README.md") -Destination (Join-Path $package "README.md")
Copy-Item -LiteralPath (Join-Path $repo "docs\REC_I_VALIDATION_BLOCKER.md") -Destination (Join-Path $package "docs\REC_I_VALIDATION_BLOCKER.md")
Copy-Item -Path (Join-Path $pythonSource "*") -Destination (Join-Path $package "runtime") -Recurse
$packagePth = Join-Path $package "runtime\python314._pth"
$pthText = [IO.File]::ReadAllText($packagePth)
if ($pthText -notmatch '(?m)^\.\.$') {
    [IO.File]::WriteAllText($packagePth, $pthText.TrimEnd("`r", "`n") + [Environment]::NewLine + ".." + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}

$files = Get-ChildItem -LiteralPath $package -File -Recurse | Sort-Object FullName | ForEach-Object {
    $relative = $_.FullName.Substring($package.Length + 1).Replace([IO.Path]::DirectorySeparatorChar, "/")
    [pscustomobject]@{
        path = $relative
        length = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$manifest = [ordered]@{
    schema = "aicadets.flight.package.v1"
    plugin_version = "0.1.8"
    target = [ordered]@{ executable = "Aottg2.exe"; architecture = "x64"; unity = "2023.1.22f1"; il2cpp_metadata = "29.1"; loader = "BepInEx 6.0.0-be.791"; runtime = ".NET 6"; receiver_python = "3.14.10 embeddable x64" }
    source_commit = $sourceCommit
    source_worktree_clean = $true
    capture_default_enabled = $false
    game_binaries_included = $false
    created_utc = [DateTime]::UtcNow.ToString("o")
    files = @($files)
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $package "package-manifest.json") -Encoding utf8
Compress-Archive -Path (Join-Path $package "*") -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "Package folder: $package"
Write-Host "Package ZIP:    $zipPath"
Write-Host "Files in manifest: $($files.Count)"
