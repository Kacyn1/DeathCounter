# Buduje dist\DS2DeathCounter.exe (jeden plik, bez okna konsoli).
# Uzycie: powershell -ExecutionPolicy Bypass -File build.ps1
# (plik celowo bez polskich znakow - Windows PowerShell 5.1 czyta skrypty jako ANSI)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    py -3.12 -m venv .venv
    & $python -m pip install --upgrade pip
}
& $python -m pip install -r requirements-dev.txt

& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Testy nie przeszly - przerwano budowanie." }

& $python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name DS2DeathCounter `
    --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets `
    --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module PySide6.QtPdf `
    --exclude-module tkinter --exclude-module pytest `
    DS2DeathCounter.pyw
if ($LASTEXITCODE -ne 0) { throw "PyInstaller zakonczyl sie bledem." }

Write-Host "Gotowe: dist\DS2DeathCounter.exe"
