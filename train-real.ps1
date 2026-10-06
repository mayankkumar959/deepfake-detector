param(
    [int]$Pairs = 2000,
    [int]$Epochs = 10,
    [int]$FineTuneEpochs = 3,
    [string]$PythonPath = $env:FORTEXA_PYTHON,
    [switch]$NoDownload
)
$ErrorActionPreference = 'Stop'
if ($Pairs -lt 20 -or $Epochs -lt 1 -or $FineTuneEpochs -lt 0) { throw 'Pairs must be >= 20, Epochs >= 1 and FineTuneEpochs >= 0.' }
if (-not $PythonPath) {
    $discoveryOutput = & node (Join-Path $PSScriptRoot 'frontend/scripts/dev.mjs') --check
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency discovery failed.' }
    $pythonLine = $discoveryOutput | Where-Object { $_ -like 'Backend Python: *' } | Select-Object -First 1
    $PythonPath = $pythonLine.Substring('Backend Python: '.Length)
}
Push-Location (Join-Path $PSScriptRoot 'backend')
try {
    & $PythonPath -c 'import torch,torchvision,cv2,sklearn'
    if ($LASTEXITCODE -ne 0) { throw 'Install backend/requirements-ml.txt with the selected interpreter.' }
    if (-not (Test-Path -LiteralPath 'data/genuine_dff/manifest.json')) {
        $prepareArgs = @('-m', 'app.ml.prepare_dff', '--pairs', "$Pairs")
        if (-not $NoDownload) { $prepareArgs += '--download' }
        & $PythonPath @prepareArgs
        if ($LASTEXITCODE -ne 0) { throw 'Dataset preparation failed; training has not started.' }
    }
    $candidatePath = 'runs/candidate-dff-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    & $PythonPath -m app.ml.train_manifest --manifest data/genuine_dff/manifest.json --out $candidatePath --arch resnet18 --epochs $Epochs --batch 16 --lr 0.001 --freeze-backbone
    if ($LASTEXITCODE -ne 0) { throw 'Training failed. The existing model was preserved.' }
    if ($FineTuneEpochs -gt 0) {
        $fineTunePath = $candidatePath + '-finetuned'
        & $PythonPath -m app.ml.train_manifest --manifest data/genuine_dff/manifest.json --out $fineTunePath --arch resnet18 --epochs $FineTuneEpochs --batch 16 --lr 0.0001 --train-last-block --init-weights "$candidatePath/model.pth"
        if ($LASTEXITCODE -ne 0) { throw "Fine-tuning failed. Baseline candidate remains in $candidatePath; production model was preserved." }
        $candidatePath = $fineTunePath
    }
    Write-Host "Training completed. Review backend/$candidatePath/evaluation.json before activation."
    Write-Host 'Existing production model was preserved; this candidate is not automatically activated.'
} finally {
    Pop-Location
}
