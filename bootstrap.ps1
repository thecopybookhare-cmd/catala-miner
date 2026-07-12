# CatalàMiner — instalación de UN comando (Windows, PowerShell). Clona el repo
# y lo instala todo. Uso (repo público):
#   irm https://raw.githubusercontent.com/thecopybookhare-cmd/catala-miner/main/bootstrap.ps1 | iex
# (si el repo es privado, clónalo tú y ejecuta install.ps1)
$ErrorActionPreference = "Stop"

$Repo = if ($env:CATALAMINER_REPO) { $env:CATALAMINER_REPO } else { "https://github.com/thecopybookhare-cmd/catala-miner.git" }
$Dest = if ($env:CATALAMINER_HOME) { $env:CATALAMINER_HOME } else { Join-Path $env:USERPROFILE "CatalaMiner" }

Write-Host "== CatalaMiner - instalacion de un comando =="
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Host "Necesitas 'git': instala Git for Windows (https://git-scm.com/download/win) o 'winget install Git.Git'." -ForegroundColor Yellow
  exit 1
}

if (Test-Path (Join-Path $Dest ".git")) {
  Write-Host "-- Actualizando copia en $Dest --"
  git -C $Dest pull --ff-only
} else {
  Write-Host "-- Clonando en $Dest --"
  git clone --depth 1 $Repo $Dest
}

Set-Location $Dest
powershell -ExecutionPolicy Bypass -File .\install.ps1
