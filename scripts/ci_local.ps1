$ErrorActionPreference = "Stop"
Write-Host "Running tests..." -ForegroundColor Cyan
python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Checking AST goldens..." -ForegroundColor Cyan
python scripts/check_goldens.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "`nLocal CI OK ✅" -ForegroundColor Green
