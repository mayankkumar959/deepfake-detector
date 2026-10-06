# Fortexa - Start both frontend and backend
# Run from project root: powershell -ExecutionPolicy Bypass -File start.ps1
Push-Location (Join-Path $PSScriptRoot 'frontend')
try { npm run dev } finally { Pop-Location }
exit $LASTEXITCODE
