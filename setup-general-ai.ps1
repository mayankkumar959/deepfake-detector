$ErrorActionPreference = 'Stop'
$modelFolder = Join-Path $PSScriptRoot 'backend/runs/general-ai-trained-indoor-20261005'
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
Write-Output 'Local research model verified. See GENERAL_AI_STATUS.md for measured limits.'
