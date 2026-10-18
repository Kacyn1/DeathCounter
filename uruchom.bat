@echo off
rem Uruchamia DS2 Death Counter ze zrodel. Przy pierwszym uruchomieniu przygotowuje srodowisko.
setlocal
cd /d "%~dp0"

if not exist ".venv\.ds2-ready" (
    echo DS2 Death Counter - pierwsze uruchomienie: przygotowanie srodowiska...
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
    if errorlevel 1 goto :error
)

start "" ".venv\Scripts\pythonw.exe" "%~dp0DS2DeathCounter.pyw"
exit /b 0

:error
echo.
echo Nie udalo sie przygotowac srodowiska - opis bledu powyzej.
pause
exit /b 1
