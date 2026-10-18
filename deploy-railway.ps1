param(
    [switch]$StageOnly,
    [string]$ModelDir = 'runs/active-image-video-20261018'
)

$ErrorActionPreference = 'Stop'
$taskRepoRoot = $PSScriptRoot
$taskStageRoot = Join-Path ([IO.Path]::GetTempPath()) ('fortexa-railway-source-' + [guid]::NewGuid().ToString('N'))
$taskFiles = & git -C $taskRepoRoot ls-files -- backend
if ($LASTEXITCODE -ne 0) { throw 'Cannot enumerate tracked backend source.' }

# Copy only tracked application/config files. Never upload local credentials,
# training data, uploads, virtual environments or the large binary weights.
New-Item -ItemType Directory -Path $taskStageRoot | Out-Null
$taskModelPattern = '^backend/' + [regex]::Escape($ModelDir.TrimEnd('/')) + '/'
foreach ($taskFile in $taskFiles) {
    if ($taskFile -notmatch '^backend/(app/|Dockerfile$|requirements(-ml)?\.txt$|\.dockerignore$)') {
        if ($taskFile -notmatch $taskModelPattern) { continue }
    }
    if ($taskFile -match '(^|/)\.env($|\.)' -or $taskFile.EndsWith('/model.safetensors')) { continue }
    $taskDestination = Join-Path $taskStageRoot $taskFile.Substring('backend/'.Length)
    New-Item -ItemType Directory -Path (Split-Path -Parent $taskDestination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $taskRepoRoot $taskFile) -Destination $taskDestination
}

$taskRequired = @(
    'Dockerfile',
    'app/main.py',
    'app/ml/general_video.py',
    (Join-Path $ModelDir 'config.json'),
    (Join-Path $ModelDir 'model_meta.json')
)
# A model folder may be image-only; the runtime then falls back to per-frame
# image scores with an explicit warning. If the local folder has a video head,
# require both video artifacts so a half-packaged upload cannot ship.
$taskLocalModel = Join-Path $taskRepoRoot (Join-Path 'backend' $ModelDir)
if (Test-Path -LiteralPath (Join-Path $taskLocalModel 'video_head.joblib')) {
    $taskRequired += @(
        (Join-Path $ModelDir 'video_head.joblib'),
        (Join-Path $ModelDir 'video_meta.json')
    )
}
foreach ($taskPath in $taskRequired) {
    if (-not (Test-Path -LiteralPath (Join-Path $taskStageRoot $taskPath))) {
        throw "Deployment source is incomplete: $taskPath"
    }
}
Write-Output "Secret-free source staging folder: $taskStageRoot"
Write-Output 'The Docker build downloads commit-pinned image weights and verifies SHA256.'
if (-not $StageOnly) {
    & railway up $taskStageRoot --path-as-root --project a9a43bc6-fd03-4656-a5c3-722682aa77ee --service 8417e469-a3db-4e58-a34f-e98de44bd470 --environment production --detach
    if ($LASTEXITCODE -ne 0) { throw 'Railway upload failed.' }
    Write-Output 'Upload accepted; inspect deployment status and logs before declaring it ready.'
}
