# Przygotowuje srodowisko .venv (Python 3.12 lub nowszy) i instaluje biblioteki.
# Uzycie: powershell -ExecutionPolicy Bypass -File setup.ps1 [-Dev]
#   -Dev  dodatkowo instaluje narzedzia do testow i budowania .exe
# (plik celowo bez polskich znakow - Windows PowerShell 5.1 czyta skrypty jako ANSI)
param([switch]$Dev)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPython = ".\.venv\Scripts\python.exe"
$readyMarker = ".\.venv\.ds2-ready"

function Find-Python {
    # Najpierw 3.12 (wersja z wymagan), potem najnowszy zainstalowany Python 3.
    $candidates = @(@("py", "-3.12"), @("py", "-3"), @("python"))
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $rest = @()
        if ($candidate.Length -gt 1) { $rest = $candidate[1..($candidate.Length - 1)] }
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $version = & $exe @rest -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        } catch {
            continue
        }
        if ($LASTEXITCODE -eq 0 -and $version -and ([version]$version -ge [version]"3.12")) {
            return ,$candidate
        }
    }
    return $null
}

if (-not (Test-Path $venvPython)) {
    $python = Find-Python
    if (-not $python) {
        throw ("Nie znaleziono Pythona 3.12 lub nowszego. Zainstaluj go ze strony " +
               "https://www.python.org/downloads/ (zostaw zaznaczone 'py launcher'), a potem uruchom ponownie.")
    }
    $exe = $python[0]
    $rest = @()
    if ($python.Length -gt 1) { $rest = $python[1..($python.Length - 1)] }
    Write-Host "Tworzenie srodowiska .venv ($exe $rest)..."
    & $exe @rest -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Nie udalo sie utworzyc srodowiska .venv." }
}

Write-Host "Instalowanie bibliotek (przy pierwszym razie moze to potrwac kilka minut)..."
& $venvPython -m pip install --disable-pip-version-check --upgrade pip | Out-Null
$requirements = "requirements.txt"
if ($Dev) { $requirements = "requirements-dev.txt" }
& $venvPython -m pip install --disable-pip-version-check -r $requirements
if ($LASTEXITCODE -ne 0) {
    throw ("Instalacja bibliotek nie powiodla sie - szczegoly powyzej. Sprawdz polaczenie z internetem; " +
           "jesli blad mowi o dlugich sciezkach (long path), przenies folder programu blizej dysku, np. C:\DS2DeathCounter.")
}

Set-Content -Path $readyMarker -Value "ok" -Encoding ascii
Write-Host "Srodowisko gotowe."
