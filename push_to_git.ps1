# SmartPark - Quick Push to Git Script
# Đẩy code lên: https://github.com/DragionTaLion/SMARTPARK

Write-Host "--- Dang chuan bi day code len GitHub ---" -ForegroundColor Cyan

# 1. Kiem tra xem da co .git chua
if (!(Test-Path ".git")) {
    git init
    Write-Host "Initialized empty Git repository." -ForegroundColor Gray
}

# 2. Cau hinh Remote (neu chua co)
$remoteUrl = "https://github.com/DragionTaLion/SMARTPARK.git"
git remote remove origin 2>$null
git remote add origin $remoteUrl

# 3. Add file (se tu dong bo qua cac file trong .gitignore)
git add .

# 4. Commit
$msg = "Upgrade SmartPark to v2.1 Pro - Clean Code & Training Guide"
git commit -m $msg

# 5. Day len branch main
Write-Host "Dang day code len branch 'main'..." -ForegroundColor Yellow
git branch -M main
git push -u origin main -f # Dung -f de dam bao day len nhanh va ghi de neu can

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   DA DAY CODE LEN GITHUB THANH CONG!   " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Link: https://github.com/DragionTaLion/SMARTPARK" -ForegroundColor Cyan
