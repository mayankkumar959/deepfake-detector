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

function Invoke-Step([string]$name, [string[]]$arguments) {
    Write-Log "step: python $($arguments -join ' ')"
    $output = & python @arguments 2>&1
    $code = $LASTEXITCODE
    $output | ForEach-Object { Write-Log $_ }
    if ($code -ne 0) {
        Write-Log "$name failed: exit $code"
        exit $code
    }
    Write-Log "$name completed"
}

# Native stderr from python used to abort the earlier chain because
# $ErrorActionPreference was 'Stop'. Downloads are already complete enough for
# v3 (Lipsync-A selection is cached), so this script only finishes the model.
Write-Log 'remaining chain started: manifest audit -> new features -> full training'
Invoke-Step 'prepare_video_v3' @('prepare_video_v3.py')
Invoke-Step 'features' @('train_video_v3.py', '--features-only')
Invoke-Step 'training' @('train_video_v3.py')
Write-Log 'video v3 training and report completed'
