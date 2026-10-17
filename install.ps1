# custom-claude-glance installer for Windows (PowerShell 5.1+)
#
#   One-liner (global):
#     irm https://raw.githubusercontent.com/trongld230289/custom-claude-glance/main/install.ps1 | iex
#   One-liner with options:
#     & ([scriptblock]::Create((irm https://raw.githubusercontent.com/trongld230289/custom-claude-glance/main/install.ps1))) -AllAccounts
#   From a clone:
#     .\install.ps1 [-Project [-Path <folder>]] [-AllAccounts] [-Uninstall]

param(
    [switch]$Project,
    [string]$Path = (Get-Location).Path,
    [switch]$AllAccounts,
    [switch]$Uninstall
)
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$Repo = "trongld230289/custom-claude-glance"
$Branch = "main"

# Find Python 3 (prefer the py launcher; "python" can be the Microsoft Store stub)
$py = $null
foreach ($c in @("py", "python", "python3")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) {
    Write-Host "Python 3 was not found. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then run this again." -ForegroundColor Red
    exit 1
}

# Use the local clone if we are inside one, otherwise download the two files
$src = $null
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "glance.py"))) {
    $src = $PSScriptRoot
} else {
    $src = Join-Path ([IO.Path]::GetTempPath()) "custom-claude-glance"
    New-Item -ItemType Directory -Force -Path $src | Out-Null
    foreach ($f in @("glance.py", "install.py")) {
        Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/$Repo/$Branch/$f" -OutFile (Join-Path $src $f)
    }
}

$a = @((Join-Path $src "install.py"))
if ($Project)     { $a += @("--project", $Path) }
if ($AllAccounts) { $a += "--all-accounts" }
if ($Uninstall)   { $a += "--uninstall" }

$env:PYTHONIOENCODING = "utf-8"
if ($py -eq "py") { & py -3 @a } else { & $py @a }
