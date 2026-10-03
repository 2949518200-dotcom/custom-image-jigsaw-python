$ErrorActionPreference = "Stop"

Write-Host "Installing dependencies..." -ForegroundColor Cyan
python -m pip install -r requirements.txt

Write-Host "Running self-test..." -ForegroundColor Cyan
python .\jigsaw_game.py --self-test

Write-Host "Building Windows executable..." -ForegroundColor Cyan
python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onefile `
  --name "CustomImageJigsaw" `
  .\jigsaw_game.py

Write-Host ""
Write-Host "Build complete: dist\CustomImageJigsaw.exe" -ForegroundColor Green
