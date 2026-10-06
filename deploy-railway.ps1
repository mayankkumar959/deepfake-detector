param([switch]$StageOnly)

$ErrorActionPreference = 'Stop'
$taskRepoRoot = $PSScriptRoot
$taskStageRoot = Join-Path ([IO.Path]::GetTempPath()) ('fortexa-railway-source-' + [guid]::NewGuid().ToString('N'))
$taskFiles = & git -C $taskRepoRoot ls-files -- backend
if ($LASTEXITCODE -ne 0) { throw 'Cannot enumerate tracked backend source.' }

# Copy only tracked application/config files. Never upload local credentials,
# training data, uploads, virtual environments or the large binary weights.
New-Item -ItemType Directory -Path $taskStageRoot | Out-Null
foreach ($taskFile in $taskFiles) {
    if ($taskFile -notmatch '^backend/(app/|runs/general-ai-trained-indoor-20261005/|Dockerfile$|requirements(-ml)?\.txt$|\.dockerignore$)') { continue }
    if ($taskFile -match '(^|/)\.env($|\.)' -or $taskFile.EndsWith('/model.safetensors')) { continue }
    $taskDestination = Join-Path $taskStageRoot $taskFile.Substring('backend/'.Length)
    New-Item -ItemType Directory -Path (Split-Path -Parent $taskDestination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $taskRepoRoot $taskFile) -Destination $taskDestination
}

foreach ($taskRequired in @('Dockerfile', 'app/main.py', 'runs/general-ai-trained-indoor-20261005/config.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $taskStageRoot $taskRequired))) {
        throw "Deployment source is incomplete: $taskRequired"
    }
}
Write-Output "Secret-free source staging folder: $taskStageRoot"
Write-Output 'The Docker build downloads commit-pinned weights and verifies SHA256.'
if (-not $StageOnly) {
    & railway up $taskStageRoot --path-as-root --project a9a43bc6-fd03-4656-a5c3-722682aa77ee --service 8417e469-a3db-4e58-a34f-e98de44bd470 --environment production --detach
    if ($LASTEXITCODE -ne 0) { throw 'Railway upload failed.' }
    Write-Output 'Upload accepted; inspect deployment status and logs before declaring it ready.'
}
