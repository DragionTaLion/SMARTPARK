# SmartPark — Khởi động toàn bộ hệ thống
# Chạy: .\start.ps1

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "   SMARTPARK ALPR - KHOI DONG HE THONG" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# Kiểm tra FastAPI dependencies
$deps = py -c "import fastapi, uvicorn" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Dang cai dat dependencies..." -ForegroundColor Yellow
    py -m pip install fastapi "uvicorn[standard]" python-multipart pyserial --quiet
}

# Khởi động FastAPI server trong background
Write-Host "[1/2] Khoi dong FastAPI Backend (localhost:8000)..." -ForegroundColor Green
$backend = Start-Process -FilePath "py" -ArgumentList "api_server.py" -PassThru -NoNewWindow
Write-Host "      PID: $($backend.Id)" -ForegroundColor DarkGray

# Đợi server sẵn sàng
Write-Host "      Doi server san sang..." -ForegroundColor DarkGray
Start-Sleep -Seconds 4

# Kiểm tra health
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -TimeoutSec 5
    Write-Host "      DB  : $($health.db)" -ForegroundColor DarkGray
    Write-Host "      YOLO: $($health.yolo)" -ForegroundColor DarkGray
    Write-Host "      GPU : $($health.gpu)" -ForegroundColor DarkGray
    Write-Host "      [OK] Backend dang chay!" -ForegroundColor Green
} catch {
    Write-Host "      [!] Backend chua san sang, thu lai sau..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[2/2] Khoi dong Frontend (localhost:3000)..." -ForegroundColor Green
Write-Host ""
Write-Host "Truy cap: http://localhost:3000" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Nhan Ctrl+C de dung ca hai..." -ForegroundColor DarkGray
Write-Host ""

try {
    npm run dev
} finally {
    Write-Host ""
    Write-Host "Dang dung backend (PID $($backend.Id))..." -ForegroundColor Yellow
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
    Write-Host "Da dung." -ForegroundColor Green
}
