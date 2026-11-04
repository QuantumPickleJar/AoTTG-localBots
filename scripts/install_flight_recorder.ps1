param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,
    [Parameter(Mandatory = $true)]
    [string]$PackageRoot
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $GameRoot).Path
$gameExecutable = [IO.Path]::GetFullPath((Join-Path $root "Aottg2.exe"))
$runningGames = @(Get-CimInstance Win32_Process -Filter "Name = 'Aottg2.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ExecutablePath -and [string]::Equals(
        [IO.Path]::GetFullPath($_.ExecutablePath), $gameExecutable, [StringComparison]::OrdinalIgnoreCase) })
if ($runningGames.Count -gt 0) {
    throw "Close this AoTTG2 game copy before installing or replacing the recorder. No files were changed: $gameExecutable"
}
$package = (Resolve-Path -LiteralPath $PackageRoot).Path
$pluginsRoot = Join-Path $root "BepInEx\plugins"
$target = Join-Path $pluginsRoot "AoTTG2FlightRecorder"
$source = Join-Path $package "plugin"
$packageManifestPath = Join-Path $package "package-manifest.json"
if (-not (Test-Path -LiteralPath $packageManifestPath -PathType Leaf)) { throw "Package manifest is missing: $packageManifestPath" }
$packageManifest = Get-Content -LiteralPath $packageManifestPath -Raw | ConvertFrom-Json
if ($packageManifest.schema -ne "aicadets.flight.package.v1" -or $packageManifest.plugin_version -ne "0.1.10") {
    throw "Package manifest schema or plugin version is not supported."
}
foreach ($file in $packageManifest.files) {
    if ($file.path -match '(^|[/\\])\.\.([/\\]|$)' -or [IO.Path]::IsPathRooted($file.path)) {
        throw "Unsafe path in package manifest: $($file.path)"
    }
    $packageFile = Join-Path $package $file.path.Replace("/", [IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $packageFile -PathType Leaf)) { throw "Package file is missing: $packageFile" }
    $packageItem = Get-Item -LiteralPath $packageFile
    $packageHash = (Get-FileHash -LiteralPath $packageFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($packageItem.Length -ne [long]$file.length -or $packageHash -ne $file.sha256) {
        throw "Package file failed SHA-256 verification: $packageFile"
    }
}

foreach ($path in @(
    (Join-Path $root "Aottg2.exe"),
    (Join-Path $root "BepInEx\core\BepInEx.Unity.IL2CPP.dll"),
    (Join-Path $root "BepInEx\interop\Scripts.dll"),
    (Join-Path $source "AoTTG2.FlightRecorder.dll"),
    (Join-Path $source "FlightRecorder.TransportClient.dll")
)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required file is missing: $path" }
}
$loaderLog = Join-Path $root "BepInEx\LogOutput.log"
if (-not (Test-Path -LiteralPath $loaderLog -PathType Leaf)) { throw "BepInEx startup log is missing: $loaderLog" }
$logText = Get-Content -LiteralPath $loaderLog -Raw
if ($logText -notmatch 'Built from commit b782da4ac54e1072d2857f4a2f77c80c3ef08005' -or
    $logText -notmatch 'Running under Unity 2023\.1\.22f1' -or
    $logText -notmatch 'Chainloader startup complete') {
    throw "Installed loader log does not match the audited BepInEx / Unity 2023.1.22f1 startup. No files were copied."
}
if (Test-Path -LiteralPath $target) {
    $existingManifestPath = Join-Path $target "install-manifest.json"
    if (-not (Test-Path -LiteralPath $existingManifestPath -PathType Leaf)) {
        throw "An unmanaged recorder folder exists without an install manifest. Review it manually; nothing was removed: $target"
    }
    $existingManifest = Get-Content -LiteralPath $existingManifestPath -Raw | ConvertFrom-Json
    $existingVersion = [string]$existingManifest.plugin_version
    $removeScript = Join-Path $PSScriptRoot "remove_flight_recorder.ps1"
    if (-not (Test-Path -LiteralPath $removeScript -PathType Leaf)) {
        throw "The guarded removal script is missing; the existing install was left untouched: $removeScript"
    }
    Write-Host "Found recorder version $existingVersion. Verifying its manifest and installed DLL hashes before replacement."
    & $removeScript -GameRoot $root
    if (Test-Path -LiteralPath $target) {
        throw "The verified existing recorder folder was not removed; no new files were installed: $target"
    }
}

New-Item -ItemType Directory -Path $pluginsRoot -Force | Out-Null
New-Item -ItemType Directory -Path $target | Out-Null
$copiedPaths = [System.Collections.Generic.List[string]]::new()
try {
    $records = @()
    foreach ($name in @("AoTTG2.FlightRecorder.dll", "FlightRecorder.TransportClient.dll")) {
        $destination = Join-Path $target $name
        Copy-Item -LiteralPath (Join-Path $source $name) -Destination $destination
        $copiedPaths.Add($destination)
        $hash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        $length = (Get-Item -LiteralPath $destination).Length
        $records += [pscustomobject]@{ path = $name; length = $length; sha256 = $hash }
    }
    $manifest = [ordered]@{
        schema = "aicadets.flight.plugin-install.v1"
        plugin_version = "0.1.10"
        install_root_relative = "BepInEx/plugins/AoTTG2FlightRecorder"
        files = $records
    }
    $manifestPath = Join-Path $target "install-manifest.json"
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding utf8
    Write-Host "Installed Flight Recorder 0.1.10. Only the two recorder DLLs were added; the BepInEx configuration was left unchanged."
    Write-Host "Rollback manifest: $manifestPath"
}
catch {
    foreach ($path in $copiedPaths) { if (Test-Path -LiteralPath $path -PathType Leaf) { Remove-Item -LiteralPath $path -Force } }
    if (Test-Path -LiteralPath $target -PathType Container -and -not (Get-ChildItem -LiteralPath $target -Force)) {
        Remove-Item -LiteralPath $target -Force
    }
    throw
}
