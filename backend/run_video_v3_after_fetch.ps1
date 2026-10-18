# Native python stderr must never abort the chain: with 'Stop', a plain
# download error message became a terminating NativeCommandError.
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$env:OMP_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$log = Join-Path $PSScriptRoot 'runs/candidate-video-v3-20261018/chain.log'
New-Item -ItemType Directory -Path (Split-Path -Parent $log) -Force | Out-Null

function Write-Log([string]$message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message"
    Write-Output $line
    Add-Content -LiteralPath $log -Value $line -Encoding utf8
}

Write-Log 'chain started: waiting for the current video feature extraction to finish'
while (Get-Process -Id 28384 -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds 30
}

$featureStatus = Get-Content 'runs/candidate-video-v3-20261018/training_status.json' -Raw |
    ConvertFrom-Json
if ($featureStatus.status -notin @('features_ready', 'finished_experimental')) {
    Write-Log "current feature run did not finish cleanly: $($featureStatus.status); stopping chain"
    exit 2
}
Write-Log 'current feature run finished; waiting for the remaining dataset downloads'

while ($true) {
    $fetch = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'fetch_new_datasets\.py' }
    if (-not $fetch) { break }
    Start-Sleep -Seconds 60
}
Write-Log 'fetch process exited; checking the download log before rebuilding the manifest'

$groups = @('openfake_tiny', 'tiny_genimage', 'openforensics_val', 'df40_img_swap',
    'shareveo3', 'genvidbench_small', 'df40_vid_lipsync', 'talkingheadbench',
    'lipsync_a', 'aigvdbench_small', 'df40_vid_swap', 'aigvdbench_gen2', 'hdtf_real')
$lastStatus = @{}
$logPath = 'data/new-datasets/download_log.jsonl'
if (Test-Path $logPath) {
    Get-Content $logPath | ForEach-Object {
        try {
            $entry = $_ | ConvertFrom-Json
            if ($entry.group) { $lastStatus[$entry.group] = $entry.status }
        } catch {}
    }
}
$failedGroups = @($groups | Where-Object { $lastStatus[$_] -ne 'ok' })
if ($failedGroups.Count -gt 0) {
    Write-Log "retrying incomplete downloads: $($failedGroups -join ', ')"
    $retryOutput = & python fetch_new_datasets.py @failedGroups 2>&1
    $retryCode = $LASTEXITCODE
    $retryOutput | ForEach-Object { Write-Log $_ }
    if ($retryCode -ne 0) { Write-Log "download retry failed: $retryCode" }
}

Write-Log 'rebuilding the video v3 manifest'
& python prepare_video_v3.py 2>&1 | ForEach-Object { Write-Log $_ }
if ($LASTEXITCODE -ne 0) { Write-Log "prepare_video_v3 failed: $LASTEXITCODE"; exit 3 }

Write-Log 'manifest rebuilt; extracting features for newly added clips'
& python train_video_v3.py --features-only 2>&1 | ForEach-Object { Write-Log $_ }
if ($LASTEXITCODE -ne 0) { Write-Log "feature extraction failed: $LASTEXITCODE"; exit 4 }

Write-Log 'features ready; starting the full video v3 training and fresh-test report'
& python train_video_v3.py 2>&1 | ForEach-Object { Write-Log $_ }
if ($LASTEXITCODE -ne 0) { Write-Log "video v3 training failed: $LASTEXITCODE"; exit 5 }

Write-Log 'video v3 training and report completed'
