# Fortexa - Start both frontend and backend
# Run from project root: powershell -ExecutionPolicy Bypass -File start.ps1

Write-Host "Starting Fortexa Deepfake Detection Platform..." -ForegroundColor Cyan

# Start backend
Write-Host "[1/2] Starting backend on http://localhost:8000" -ForegroundColor Green
$backend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; python -m uvicorn app.main:app --reload" -PassThru

# Wait for backend to start
Start-Sleep -Seconds 3

# Start frontend
Write-Host "[2/2] Starting frontend on http://localhost:5173" -ForegroundColor Green
$frontend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev" -PassThru

Write-Host "`n✓ Both services running!" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Gray
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Gray
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "`nPress Ctrl+C in each window to stop." -ForegroundColor Yellow

# Keep script alive
Read-Host "`nPress Enter to stop both services..."

# Cleanup
Stop-Process $backend.Id -Force -ErrorAction SilentlyContinue
Stop-Process $frontend.Id -Force -ErrorAction SilentlyContinue
Write-Host "Stopped." -ForegroundColor Red