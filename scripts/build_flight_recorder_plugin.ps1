param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $GameRoot).Path
$required = @(
    (Join-Path $root "Aottg2.exe"),
    (Join-Path $root "BepInEx\core\BepInEx.Unity.IL2CPP.dll"),
    (Join-Path $root "BepInEx\interop\Scripts.dll"),
    (Join-Path $root "BepInEx\interop\UnityEngine.CoreModule.dll"),
    (Join-Path $root "BepInEx\interop\UnityEngine.PhysicsModule.dll")
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required installed-game or generated interop file is missing: $path"
    }
}
$loaderLog = Join-Path $root "BepInEx\LogOutput.log"
if (-not (Test-Path -LiteralPath $loaderLog -PathType Leaf)) { throw "BepInEx startup log is missing: $loaderLog" }
$logText = Get-Content -LiteralPath $loaderLog -Raw
if ($logText -notmatch 'Running under Unity 2023\.1\.22f1' -or
    $logText -notmatch 'Chainloader startup complete') {
    throw "BepInEx log does not prove the audited Unity 2023.1.22f1 startup."
}

$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$transportProject = Join-Path $repo "plugin\FlightRecorder.TransportClient\FlightRecorder.TransportClient.csproj"
$pluginProject = Join-Path $repo "plugin\FlightRecorder.UnityIl2Cpp\FlightRecorder.UnityIl2Cpp.csproj"

& dotnet build $transportProject --configuration $Configuration -f net6.0
if ($LASTEXITCODE -ne 0) { throw "Transport client build failed with exit code $LASTEXITCODE." }

& dotnet build $pluginProject --configuration $Configuration "-p:GameRoot=$root"
if ($LASTEXITCODE -ne 0) { throw "Unity IL2CPP plugin build failed with exit code $LASTEXITCODE." }

Write-Host "Built against installed interop for Unity 2023.1.22f1 / x64."
Write-Host (Join-Path $repo "plugin\FlightRecorder.UnityIl2Cpp\bin\$Configuration\net6.0\AoTTG2.FlightRecorder.dll")
