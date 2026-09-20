Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Starting Complete Tauri Development Environment" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] Checking for existing processes on ports 5050 and 5173..." -ForegroundColor Yellow
foreach ($port in @("5050", "5173")) {
    try {
        $existing = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($existing) {
            foreach ($conn in $existing) {
                if ($conn.OwningProcess -and $conn.OwningProcess -gt 0) {
                    Write-Host "Terminating process on port $port (PID: $($conn.OwningProcess))..." -ForegroundColor Yellow
                    taskkill /F /T /PID $conn.OwningProcess 2>$null | Out-Null
                    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                }
            }
            Start-Sleep -Milliseconds 400
        }
    } catch {
        Write-Host "No process on port $port" -ForegroundColor Gray
    }
}

try {
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path -like "*Python*" } | ForEach-Object {
        try {
            $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
            if ($cmd -and $cmd -like "*backend/app.py*") {
                Write-Host "Terminating orphaned backend process (PID: $($_.Id))..." -ForegroundColor Yellow
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }
    foreach ($driver in @("chromedriver", "geckodriver", "msedgedriver")) {
        Get-Process -Name $driver -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
} catch {}

Write-Host "[2/4] Starting Python Backend Server (Console Window)..." -ForegroundColor Yellow
$pythonProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "title Python Backend (Port 5050) && python -u backend/app.py" -WorkingDirectory (Get-Location) -PassThru

Write-Host "[3/4] Waiting for backend to initialize..." -ForegroundColor Yellow
$backendReady = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:5050/api/health" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response -and $response.status -eq "healthy") {
            $backendReady = $true
            break
        }
    } catch {}
}

if ($backendReady) {
    Write-Host "[SUCCESS] Python backend is ready at http://127.0.0.1:5050" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Backend took longer than expected to initialize" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[4/4] Starting Tauri Development Application..." -ForegroundColor Yellow
Write-Host "Tauri will automatically start the Vite dev server." -ForegroundColor Gray
Write-Host ""

try {
    npm run tauri:dev
} finally {
    Write-Host ""
    Write-Host "Stopping Python backend..." -ForegroundColor Yellow
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:5050/api/system/shutdown" -Method Post -TimeoutSec 1 -ErrorAction SilentlyContinue | Out-Null
        Start-Sleep -Milliseconds 300
    } catch {}
    if ($pythonProcess -and $pythonProcess.Id) {
        taskkill /F /T /PID $pythonProcess.Id 2>$null | Out-Null
        Stop-Process -Id $pythonProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Done." -ForegroundColor Green
}