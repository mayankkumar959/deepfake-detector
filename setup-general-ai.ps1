param(
    [string]$ModelDir
)

$ErrorActionPreference = 'Stop'
$newFolder = Join-Path $PSScriptRoot 'backend/runs/active-image-video-20261018'
$oldFolder = Join-Path $PSScriptRoot 'backend/runs/general-ai-trained-indoor-20261005'
if ($ModelDir) {
    $modelFolder = Join-Path $PSScriptRoot $ModelDir
} elseif (Test-Path -LiteralPath (Join-Path $newFolder 'model_meta.json')) {
    $modelFolder = $newFolder
} else {
    $modelFolder = $oldFolder
}

$metadataPath = Join-Path $modelFolder 'model_meta.json'
if (-not (Test-Path -LiteralPath $metadataPath)) { throw 'Restore the locally trained model artifact. Upstream weights do not contain the trained head.' }
$metadata = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
foreach ($artifact in $metadata.sha256.PSObject.Properties) {
    if ($artifact.Name -notin @('model.safetensors', 'config.json', 'preprocessor_config.json')) { throw "Unexpected artifact: $($artifact.Name)" }
    $destination = Join-Path $modelFolder $artifact.Name
    if (-not (Test-Path -LiteralPath $destination)) { throw "Missing trained artifact: $($artifact.Name)" }
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $artifact.Value) { throw "Checksum mismatch: $($artifact.Name)" }
    Write-Output "Verified trained artifact: $($artifact.Name)"
}

$videoMetadataPath = Join-Path $modelFolder 'video_meta.json'
if (Test-Path -LiteralPath $videoMetadataPath) {
    $videoMetadata = Get-Content -LiteralPath $videoMetadataPath -Raw | ConvertFrom-Json
    foreach ($artifact in $videoMetadata.sha256.PSObject.Properties) {
        $destination = Join-Path $modelFolder $artifact.Name
        if (-not (Test-Path -LiteralPath $destination)) { throw "Missing trained video artifact: $($artifact.Name)" }
        if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $artifact.Value) { throw "Checksum mismatch: $($artifact.Name)" }
        Write-Output "Verified trained video artifact: $($artifact.Name)"
    }
} else {
    Write-Output 'No video head packaged with this model folder; videos fall back to per-frame image scores.'
}
Write-Output "Local research model verified: $modelFolder"
Write-Output 'See GENERAL_AI_STATUS.md and VIDEO_DETECTOR.md for measured limits.'
