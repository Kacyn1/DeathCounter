# Buduje dist\DS2DeathCounter.exe (jeden plik, bez okna konsoli).
# Uzycie: powershell -ExecutionPolicy Bypass -File build.ps1
# (plik celowo bez polskich znakow - Windows PowerShell 5.1 czyta skrypty jako ANSI)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

& "$PSScriptRoot\setup.ps1" -Dev
$python = ".\.venv\Scripts\python.exe"

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
