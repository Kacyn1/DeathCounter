# DS2 Death Counter

Lokalna aplikacja Windows, która automatycznie liczy śmierci w **Dark Souls II: Scholar of the First Sin**, rozpoznając na obrazie gry napis „NIE ŻYJESZ”. Działa offline i nie ingeruje w pliki ani pamięć gry.

## Pobranie i uruchomienie

### Sposób 1: gotowy program (zalecany)

1. Wejdź w [Releases](https://github.com/Kacyn1/ds2DeathCounter/releases) i pobierz `DS2DeathCounter.exe`.
2. Umieść go w osobnym folderze, np. `C:\Gry\LicznikDS2`. Obok programu będą zapisywane `deaths.json`, `config.json` i `template.png`.
3. Uruchom dwuklikiem. Python nie jest potrzebny.

Program nie ma podpisu cyfrowego, więc Windows może pokazać „System Windows ochronił ten komputer”. Kliknij wtedy **Więcej informacji → Uruchom mimo to**.

### Sposób 2: ze źródeł (ZIP z GitHuba)

1. Zainstaluj [Pythona](https://www.python.org/downloads/) w wersji 3.12 lub nowszej. Zostaw zaznaczoną opcję „py launcher”.
2. Pobierz repozytorium (**Code → Download ZIP**) i rozpakuj je. Najlepiej w krótkiej ścieżce, np. `C:\DS2DeathCounter`.
3. Uruchom dwuklikiem **`uruchom.bat`**. Za pierwszym razem skrypt utworzy środowisko `.venv` i pobierze biblioteki (ok. 400 MB, zwykle kilkadziesiąt sekund). Kolejne uruchomienia otwierają program od razu.

Z tego samego folderu możesz zbudować własny `.exe`: `powershell -ExecutionPolicy Bypass -File build.ps1` (wynik w `dist\DS2DeathCounter.exe`).

Jeśli folderu programu nie da się zapisywać, dane trafiają do `%APPDATA%\DS2DeathCounter`.

## Pierwsze użycie: kalibracja

1. Uruchom grę (pełny ekran lub okno).
2. Kliknij **Kalibracja…** i pobierz obraz z napisem „NIE ŻYJESZ”. Masz trzy sposoby:
   - w trakcie ekranu śmierci naciśnij **Ctrl+Alt+F9** (usłyszysz sygnał), a potem otwórz kalibrację;
   - ustaw opóźnienie i kliknij **Przechwyć ekran**;
   - wczytaj zrzut ekranu z gry (np. F12 w Steam).
3. Zaznacz myszą prostokąt obejmujący sam napis i kliknij **Sprawdź wzorzec**. Wynik powinien przekroczyć próg.
4. Kliknij **Zapisz wzorzec**, a potem **Start**.

Wzorzec warto też sprawdzić na zwykłym zrzucie z rozgrywki. Wynik powinien być tam wyraźnie niższy od progu.

## Jak działa wykrywanie

- Co ok. 0,1 s pobierana jest klatka (DXCam). Okolica miejsca napisu jest porównywana ze wzorcem (OpenCV, `TM_CCOEFF_NORMED`). Wzorzec skaluje się automatycznie do bieżącej rozdzielczości.
- **Potwierdzanie:** śmierć liczy się dopiero wtedy, gdy napis jest widoczny na 3 kolejnych próbkach.
- **Brak duplikatów:** po zliczeniu detektor czeka, aż napis zniknie na co najmniej 3 s. Między dwiema śmierciami musi też minąć co najmniej 8 s.
- **Błędy obrazu:** brak nowych klatek, zamrożony obraz (ponad 5 s) i zmiana rozdzielczości są sygnalizowane w oknie. W tym czasie nic nie jest liczone.

Próg, liczbę próbek potwierdzenia, czas ponownego uzbrojenia i monitor ustawisz w oknie. Pozostałe parametry są w `config.json` (sekcja `detector`).

## Dane

`deaths.json` zawiera wyłącznie `{ "deaths": N }` i jest zapisywany atomowo przy każdej zmianie. Uszkodzony plik zostaje odłożony jako `deaths.json.uszkodzony`.

## Gra w pełnym ekranie

DS2 nie ma trybu okna bez ramek, dlatego program jest przygotowany na pełny ekran:

- **Nakładka przez RTSS.** Zwykłe okno „na wierzchu” często nie przebija się przez ekskluzywny pełny ekran DirectX. Dlatego licznik może być wyświetlany przez [RivaTuner Statistics Server](https://www.guru3d.com/download/rtss-rivatuner-statistics-server-download/) (często instalowany razem z MSI Afterburner). Program tylko wpisuje tekst do pamięci współdzielonej RTSS, a w grze rysuje go RTSS. Wymagania:
  - RTSS jest uruchomiony;
  - „Show On-Screen Display” jest włączone;
  - w programie wybrano tryb „Okno + RTSS” albo „Tylko RTSS”.

  Pozycję, kolor i wielkość tekstu ustawia się w RTSS. Uwaga: sam RTSS, podobnie jak nakładki Steam czy Discord, podpina się pod renderowanie gry. Program licznika nie dotyka gry.
- **Automatyczna instalacja i start RTSS.** Jeśli RTSS nie jest zainstalowany, licznik przy pierwszym uruchomieniu zaproponuje instalację przez winget (paczka `Guru3D.RTSS`). Instalator RTSS poprosi wtedy o zgodę administratora. RTSS wymaga uprawnień administratora przy każdym starcie, dlatego licznik raz, za zgodą w oknie UAC, tworzy zadanie Harmonogramu zadań „DS2DeathCounter - RTSS”. Przez to zadanie uruchamia potem RTSS bez pytania. Sam licznik działa bez uprawnień administratora. Funkcję wyłącza opcja „Uruchamiaj RTSS razem z licznikiem”. Zadanie usuniesz poleceniem `schtasks /Delete /TN "DS2DeathCounter - RTSS" /F` w terminalu uruchomionym jako administrator.
- **Nakładka-okno.** Może być widoczna także w pełnym ekranie, jeśli Windows stosuje dla gry optymalizacje pełnego ekranu. We właściwościach `DarkSoulsII.exe` → Zgodność opcja „Wyłącz optymalizacje pełnego ekranu” musi być odznaczona. Trzeba to sprawdzić na swoim komputerze.
- **Skróty globalne**, bez wychodzenia z gry:
  - **Ctrl+Alt+F9** – zrzut do kalibracji;
  - **Ctrl+Alt+F10** – +1;
  - **Ctrl+Alt+F11** – −1.

  Każdy skrót potwierdza sygnał dźwiękowy.
- **Automatyczny start.** Opcja „Włączaj wykrywanie przy starcie” pozwala uruchomić licznik przed grą i nie przełączać się do jego okna.
- **Przechwytywanie obrazu** (DXGI Desktop Duplication) działa w pełnym ekranie. Gdy gra zmienia tryb ekranu albo rozdzielczość, przechwytywanie jest odtwarzane automatycznie, a wzorzec przeskalowany.

## Ograniczenia

- Skuteczność wykrywania trzeba potwierdzić na docelowym komputerze: śmierci od bossów, przeciwników, upadków i efektów obrażeń.

## Rozwój

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1 -Dev   # .venv + biblioteki + pytest/PyInstaller
.\.venv\Scripts\python.exe -m pytest -q
powershell -ExecutionPolicy Bypass -File build.ps1        # testy + dist\DS2DeathCounter.exe
```

| Skrypt | Rola |
|---|---|
| `uruchom.bat` | uruchomienie ze źródeł (przy pierwszym razie woła `setup.ps1`) |
| `setup.ps1` | tworzy `.venv` na Pythonie 3.12+ i instaluje biblioteki (`-Dev`: także narzędzia) |
| `build.ps1` | `setup.ps1 -Dev`, testy, budowa `.exe` |

| Moduł | Rola |
|---|---|
| `ds2counter/storage.py` | `deaths.json`, zapis atomowy |
| `ds2counter/config.py` | `config.json`, ścieżki |
| `ds2counter/template.py` | wzorzec napisu i dopasowanie |
| `ds2counter/detector.py` | maszyna stanów detektora, kontrola obrazu (bez Qt, testowalne) |
| `ds2counter/capture.py` | przechwytywanie DXCam |
| `ds2counter/worker.py` | wątek wykrywania |
| `ds2counter/overlay.py` | nakładka-okno (PySide6 + WinAPI) |
| `ds2counter/rtss.py` | tekst w nakładce RTSS (pamięć współdzielona) |
| `ds2counter/rtss_setup.py` | instalacja RTSS (winget) i start bez UAC (Harmonogram zadań) |
| `ds2counter/calibration.py` | okno kalibracji |
| `ds2counter/main_window.py` | okno główne |
