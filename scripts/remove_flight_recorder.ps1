param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $GameRoot).Path
$pluginsRoot = (Resolve-Path -LiteralPath (Join-Path $root "BepInEx\plugins")).Path
$target = Join-Path $pluginsRoot "AoTTG2FlightRecorder"
if (-not (Test-Path -LiteralPath $target -PathType Container)) { throw "Recorder plugin folder is not present: $target" }
$resolvedTarget = (Resolve-Path -LiteralPath $target).Path
$expectedTarget = [IO.Path]::GetFullPath((Join-Path $pluginsRoot "AoTTG2FlightRecorder"))
if (-not [string]::Equals($resolvedTarget, $expectedTarget, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing removal because the resolved target does not match the recorder folder under BepInEx/plugins."
}
$gameExecutable = [IO.Path]::GetFullPath((Join-Path $root "Aottg2.exe"))
$runningGames = @(Get-CimInstance Win32_Process -Filter "Name = 'Aottg2.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ExecutablePath -and [string]::Equals(
        [IO.Path]::GetFullPath($_.ExecutablePath), $gameExecutable, [StringComparison]::OrdinalIgnoreCase) })
if ($runningGames.Count -gt 0) {
    throw "Close this AoTTG2 game copy before removing the recorder. No files were changed: $gameExecutable"
}

$manifestPath = Join-Path $resolvedTarget "install-manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "Install manifest is missing; refusing to remove files without provenance." }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.schema -ne "aicadets.flight.plugin-install.v1" -or
    $manifest.install_root_relative -ne "BepInEx/plugins/AoTTG2FlightRecorder") {
    throw "Install manifest does not identify this recorder package."
}
$requiredNames = @("AoTTG2.FlightRecorder.dll", "FlightRecorder.TransportClient.dll")
$manifestNames = @($manifest.files | ForEach-Object { [string]$_.path })
if ($manifestNames.Count -ne $requiredNames.Count -or
    @($requiredNames | Where-Object { $_ -notin $manifestNames }).Count -ne 0) {
    throw "Install manifest does not list exactly the two recorder DLLs; refusing removal."
}

$expected = @{}
foreach ($file in $manifest.files) {
    if ($file.path -notin @("AoTTG2.FlightRecorder.dll", "FlightRecorder.TransportClient.dll")) {
        throw "Unsafe path in install manifest: $($file.path)"
    }
    $path = Join-Path $resolvedTarget $file.path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Installed file is missing; refusing partial rollback: $path" }
    $item = Get-Item -LiteralPath $path
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($item.Length -ne [long]$file.length -or $hash -ne $file.sha256) {
        throw "Installed file changed after deployment; preserve and review it manually: $path"
    }
    $expected[$item.Name] = $true
}

$extra = Get-ChildItem -LiteralPath $resolvedTarget -File -Force |
    Where-Object { $_.Name -ne "install-manifest.json" -and -not $expected.ContainsKey($_.Name) }
if ($extra) { throw "Unlisted files are present; refusing to remove the folder: $($extra.FullName -join ', ')" }
$extraDirectories = Get-ChildItem -LiteralPath $resolvedTarget -Directory -Force -Recurse
if ($extraDirectories) { throw "Unlisted directories are present; refusing to remove the folder: $($extraDirectories.FullName -join ', ')" }

foreach ($name in $expected.Keys) { Remove-Item -LiteralPath (Join-Path $resolvedTarget $name) -Force }
Remove-Item -LiteralPath $manifestPath -Force
if (-not (Get-ChildItem -LiteralPath $resolvedTarget -Force)) { Remove-Item -LiteralPath $resolvedTarget -Force }
Write-Host "Removed only unchanged manifest-listed recorder files. BepInEx and its generated interop files were left untouched."
Write-Host "Review and remove the generated BepInEx config separately if desired; it may contain user edits."
