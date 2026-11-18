[CmdletBinding()]
param(
    [string]$Repo = "hugo94z/paint-amelior",
    [string]$Branch = "main",
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "PaintAmeliore"),
    [string]$PythonExe = "",
    [switch]$NoShortcut
)

$ErrorActionPreference = "Stop"
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch {}
try { chcp 65001 | Out-Null } catch {}
$env:PYTHONIOENCODING = "utf-8"

function Step($message) { Write-Host "==> $message" -ForegroundColor Cyan }
function Ok($message) { Write-Host "    [OK] $message" -ForegroundColor Green }
function Warn($message) { Write-Host "    [!] $message" -ForegroundColor Yellow }

$script:NativeExit = 0

function Invoke-Native {
    param([string]$FilePath, [string[]]$Arguments, [switch]$Quiet)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if ($Quiet) {
            & $FilePath @Arguments 1>$null 2>$null
        } else {
            & $FilePath @Arguments
        }
        $script:NativeExit = $LASTEXITCODE
    } catch {
        $script:NativeExit = 1
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Invoke-NativeCapture {
    param([string]$FilePath, [string[]]$Arguments)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $FilePath @Arguments 2>$null
        $script:NativeExit = $LASTEXITCODE
        return (($output | Out-String).Trim())
    } finally {
        $ErrorActionPreference = $previous
    }
}

trap {
    Write-Host ""
    Write-Host "ERREUR : $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor DarkCyan
Write-Host "   Paint Ameliore - Installateur Windows" -ForegroundColor White
Write-Host "   Version 1.6.5" -ForegroundColor Gray
Write-Host "==================================================" -ForegroundColor DarkCyan
Write-Host ""

$tempRoot = Join-Path $env:TEMP ("paint-amelior-" + [guid]::NewGuid().ToString("N"))
$source = $null
$downloaded = $false

if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "run.py"))) {
    Step "Installation depuis le dossier local"
    $source = $PSScriptRoot
} else {
    $archive = Join-Path $env:TEMP "paint-amelior.zip"
    $url = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"
    Step "Telechargement de $url"
    try {
        Invoke-WebRequest -Uri $url -OutFile $archive -UseBasicParsing
        Expand-Archive -Path $archive -DestinationPath $tempRoot -Force
        $folder = Get-ChildItem -Path $tempRoot -Directory | Select-Object -First 1
        if (-not $folder) { throw "Archive vide" }
        $source = $folder.FullName
        $downloaded = $true
        Ok "Archive recuperee"
    } catch {
        Warn "Telechargement direct impossible : $($_.Exception.Message)"
        if (Get-Command git -ErrorAction SilentlyContinue) {
            Step "Nouvelle tentative avec git clone"
            Invoke-Native "git" @("clone", "--depth", "1", "--branch", $Branch, "https://github.com/$Repo.git", $tempRoot) -Quiet
            if ($script:NativeExit -ne 0) { throw "git clone a echoue. Verifiez -Repo et -Branch." }
            $source = $tempRoot
            $downloaded = $true
            Ok "Depot clone"
        } else {
            throw "Impossible de recuperer le projet depuis GitHub. Verifiez le parametre -Repo."
        }
    }
}

$appDir = Join-Path $InstallDir "app"
Step "Installation des fichiers dans $appDir"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
if (Test-Path $appDir) { Remove-Item -Path $appDir -Recurse -Force }
Copy-Item -Path $source -Destination $appDir -Recurse -Force
Get-ChildItem -Path $appDir -Recurse -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in @(".git", "__pycache__", ".venv", "venv") } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $appDir -Recurse -File -Filter "*.pyc" -Force -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue
Ok "Application copiee"

$python = $null
$pythonArgs = @()
if ($PythonExe) {
    $python = $PythonExe
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $python = (Get-Command py).Source
    $pythonArgs = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = (Get-Command python).Source
}
if (-not $python) {
    throw "Python introuvable. Installez Python 3.10 ou plus depuis https://www.python.org/downloads/"
}
$version = Invoke-NativeCapture $python ($pythonArgs + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])"))
if ($script:NativeExit -ne 0 -or -not $version -or [version]$version -lt [version]"3.10") {
    throw "Python 3.10 ou plus est requis (detecte : $version)."
}
$resolved = Invoke-NativeCapture $python ($pythonArgs + @("-c", "import sys; print(sys.executable)"))
if ($script:NativeExit -eq 0 -and $resolved -and (Test-Path $resolved)) {
    $python = $resolved
    $pythonArgs = @()
}
Ok "Python $version detecte"

$requirements = Join-Path $appDir "requirements.txt"
$venv = Join-Path $InstallDir "venv"
$venvPy = Join-Path $venv "Scripts\python.exe"
$libs = Join-Path $InstallDir "libs"
$useVenv = Test-Path $venvPy

if (-not $useVenv) {
    Step "Creation de l'environnement virtuel"
    Invoke-Native $python ($pythonArgs + @("-m", "venv", $venv)) -Quiet
    if (Test-Path $venvPy) {
        $useVenv = $true
    } else {
        Warn "Le module venv est indisponible sur ce Python"
    }
}

if ($useVenv) {
    $runPython = $venvPy
    $runPythonArgs = @()
    Step "Installation des dependances dans l'environnement virtuel"
    Invoke-Native $runPython @("-m", "pip", "install", "--upgrade", "pip", "--disable-pip-version-check", "--quiet")
    if ($script:NativeExit -ne 0) { Warn "Mise a jour de pip ignoree" }
    Invoke-Native $runPython @("-m", "pip", "install", "--disable-pip-version-check", "-r", $requirements, "--quiet")
    if ($script:NativeExit -ne 0) { throw "Installation des dependances impossible." }
    Ok "Dependances installees (venv)"
} else {
    $runPython = $python
    $runPythonArgs = $pythonArgs
    New-Item -ItemType Directory -Force -Path $libs | Out-Null
    Invoke-Native $runPython ($runPythonArgs + @("-m", "pip", "--version")) -Quiet
    if ($script:NativeExit -ne 0) {
        Invoke-Native $runPython ($runPythonArgs + @("-m", "ensurepip", "--upgrade")) -Quiet
    }
    if ($script:NativeExit -ne 0) {
        throw "pip est introuvable. Reinstallez Python en cochant pip et venv."
    }
    Step "Installation locale des dependances dans $libs"
    Invoke-Native $runPython ($runPythonArgs + @("-m", "pip", "install", "--target", $libs, "--upgrade", "--disable-pip-version-check", "-r", $requirements, "--quiet"))
    if ($script:NativeExit -ne 0) { throw "Installation locale des dependances impossible." }
    Ok "Dependances installees (libs locales)"
}

$runPy = Join-Path $appDir "run.py"
$hardwareFile = Join-Path $appDir "hardware.json"
Step "Analyse de la configuration du PC"
Invoke-Native $runPython ($runPythonArgs + @($runPy, "--hardware", "--write", $hardwareFile))
if ($script:NativeExit -ne 0) { Warn "Analyse materielle incomplete" }
if (Test-Path $hardwareFile) { Ok "hardware.json genere" }

$pythonw = Join-Path (Split-Path $runPython) "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $runPython }

$launcherPy = Join-Path $InstallDir "LancerPaint.pyw"
$libsLine = if ($useVenv) { "" } else { "sys.path.insert(0, r`"$libs`")" }
$launcherContent = @"
import sys
sys.path.insert(0, r"$appDir")
$libsLine
from paint.app import main
raise SystemExit(main())
"@
Set-Content -Path $launcherPy -Value $launcherContent -Encoding UTF8
Ok "Lanceur Python cree"

$cmdPath = Join-Path $InstallDir "Lancer Paint.cmd"
$cmdContent = "@echo off`r`nstart `"`" `"$pythonw`" `"$launcherPy`""
Set-Content -Path $cmdPath -Value $cmdContent -Encoding Default
Ok "Lanceur cree : $cmdPath"

function New-Shortcut([string]$LinkPath, [string]$Target, [string]$Arguments, [string]$WorkDir) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($LinkPath)
    $shortcut.TargetPath = $Target
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $WorkDir
    $shortcut.Description = "Paint Ameliore"
    $shortcut.IconLocation = "$Target,0"
    $shortcut.Save()
}

if (-not $NoShortcut) {
    Step "Creation des raccourcis"
    $arguments = '"' + $launcherPy + '"'
    $desktop = [Environment]::GetFolderPath("Desktop")
    if ($desktop) {
        New-Shortcut (Join-Path $desktop "Paint Ameliore.lnk") $pythonw $arguments $appDir
    }
    $programs = [Environment]::GetFolderPath("Programs")
    if ($programs) {
        $menuDir = Join-Path $programs "Paint Ameliore"
        New-Item -ItemType Directory -Force -Path $menuDir | Out-Null
        New-Shortcut (Join-Path $menuDir "Paint Ameliore.lnk") $pythonw $arguments $appDir
    }
    Ok "Raccourcis Bureau et menu Demarrer"
}

Step "Enregistrement dans Windows"
$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\PaintAmeliore"
New-Item -Path $uninstallKey -Force | Out-Null
Set-ItemProperty -Path $uninstallKey -Name "DisplayName" -Value "Paint Ameliore"
Set-ItemProperty -Path $uninstallKey -Name "DisplayVersion" -Value "1.5.0"
Set-ItemProperty -Path $uninstallKey -Name "Publisher" -Value "hugo94z"
Set-ItemProperty -Path $uninstallKey -Name "InstallLocation" -Value $InstallDir
Set-ItemProperty -Path $uninstallKey -Name "DisplayIcon" -Value "$pythonw,0"
Set-ItemProperty -Path $uninstallKey -Name "UninstallString" -Value "powershell -NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $appDir 'uninstall.ps1')`""
$classes = "HKCU:\Software\Classes"
$progId = "PaintAmeliore.paint"
New-Item -Path "$classes\$progId\shell\open\command" -Force | Out-Null
Set-Item -Path "$classes\$progId" -Value "Document Paint Ameliore"
Set-Item -Path "$classes\$progId\shell\open\command" `
    -Value "`"$pythonw`" `"$launcherPy`" `"%1`""
New-Item -Path "$classes\.paint" -Force | Out-Null
Set-Item -Path "$classes\.paint" -Value $progId
Ok "Association .paint et entree Ajout/Suppression de programmes"

if ($downloaded -and (Test-Path $tempRoot)) {
    Remove-Item -Path $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor DarkCyan
Write-Host "   Installation terminee" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor DarkCyan
Write-Host "  Dossier    : $InstallDir"
Write-Host "  Lancement  : $cmdPath"
if (-not $NoShortcut) {
    Write-Host "  Raccourci  : Bureau et menu Demarrer"
}
Write-Host "  Desinstall : powershell -ExecutionPolicy Bypass -File $appDir\uninstall.ps1"
Write-Host ""
