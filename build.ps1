[CmdletBinding()]
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $SkipInstall) {
    Write-Host "Installation des dependances de build..." -ForegroundColor Cyan
    python -m pip install --disable-pip-version-check -r requirements.txt pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "Installation des dependances impossible." }
}

Write-Host "Construction de l'executable..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean --windowed --name "Paint Ameliore" --collect-all psd_tools run.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller a echoue." }

$dist = Join-Path $PSScriptRoot "dist"
$folder = Join-Path $dist "Paint Ameliore"
if (-not (Test-Path $folder)) { throw "Dossier de sortie introuvable." }

$zip = Join-Path $dist "Paint-Ameliore-win64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $folder "*") -DestinationPath $zip -CompressionLevel Optimal
Write-Host "Archive : $zip" -ForegroundColor Green
Write-Host "Executable : $(Join-Path $folder 'Paint Ameliore.exe')" -ForegroundColor Green
