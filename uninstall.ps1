[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "PaintAmeliore"),
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "Desinstallation de Paint Ameliore" -ForegroundColor Cyan
if (-not (Test-Path $InstallDir)) {
    Write-Host "Dossier introuvable : $InstallDir" -ForegroundColor Yellow
    exit 0
}

if (-not $Force) {
    $answer = Read-Host "Supprimer $InstallDir et ses raccourcis ? (o/n)"
    if ($answer -notin @("o", "O", "oui", "Oui", "y", "Y")) {
        Write-Host "Annule."
        exit 0
    }
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = Join-Path $desktop "Paint Ameliore.lnk"
if (Test-Path $shortcut) { Remove-Item $shortcut -Force }

$programs = [Environment]::GetFolderPath("Programs")
$menuDir = Join-Path $programs "Paint Ameliore"
if (Test-Path $menuDir) { Remove-Item $menuDir -Recurse -Force }

Remove-Item -Path $InstallDir -Recurse -Force
Write-Host "Paint Ameliore a ete desinstalle." -ForegroundColor Green
