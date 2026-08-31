# Border Control Screening System — one-command local startup (Windows)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "Starting FastAPI backend on http://localhost:8000 ..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root'; python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"
) | Out-Null

Start-Sleep -Seconds 3

Write-Host "Starting Vite frontend on http://localhost:5173 ..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root\frontend'; npm run dev -- --host 127.0.0.1 --port 5173"
) | Out-Null

Write-Host ""
Write-Host "Both servers launching in separate windows."
Write-Host "  Backend : http://localhost:8000/health"
Write-Host "  Frontend: http://localhost:5173"
Write-Host ""
Write-Host "First /verify call may take 30-60s while AI models load."
