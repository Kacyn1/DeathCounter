# Death Counter

Lokalna aplikacja Windows, która automatycznie liczy śmierci w grach wyświetlających po śmierci charakterystyczny napis, np. „NIE ŻYJESZ” / „YOU DIED” w serii Dark Souls, Elden Ring czy Sekiro. Program rozpoznaje ten napis na obrazie gry na podstawie wzorca z kalibracji. Działa offline i nie ingeruje w pliki ani pamięć gry.

## Pobranie i uruchomienie

### Sposób 1: gotowy program (zalecany)

1. Wejdź w [Releases](https://github.com/Kacyn1/DeathCounter/releases) i pobierz `DeathCounter.exe`.
2. Umieść go w osobnym folderze, np. `C:\Gry\DeathCounter`. Obok programu będą zapisywane `deaths.json`, `bosses.json`, `config.json` i wzorce (`template.png`, `boss_bar.png`, `victory.png`).
3. Uruchom dwuklikiem. Python nie jest potrzebny.

Program nie ma podpisu cyfrowego, więc Windows może pokazać „System Windows ochronił ten komputer”. Kliknij wtedy **Więcej informacji → Uruchom mimo to**.

### Sposób 2: ze źródeł (ZIP z GitHuba)

1. Zainstaluj [Pythona](https://www.python.org/downloads/) w wersji 3.12 lub nowszej. Zostaw zaznaczoną opcję „py launcher”.
2. Pobierz repozytorium (**Code → Download ZIP**) i rozpakuj je. Najlepiej w krótkiej ścieżce, np. `C:\DeathCounter`.
3. Uruchom dwuklikiem **`uruchom.bat`**. Za pierwszym razem skrypt utworzy środowisko `.venv` i pobierze biblioteki (ok. 400 MB, zwykle kilkadziesiąt sekund). Kolejne uruchomienia otwierają program od razu.

Z tego samego folderu możesz zbudować własny `.exe`: `powershell -ExecutionPolicy Bypass -File build.ps1` (wynik w `dist\DeathCounter.exe`).

Jeśli folderu programu nie da się zapisywać, dane trafiają do `%APPDATA%\DeathCounter`.

## Pierwsze użycie: kalibracja

1. Uruchom grę (pełny ekran lub okno).
2. Kliknij **Kalibracja…** i pobierz obraz z napisem po śmierci (np. „NIE ŻYJESZ”). Masz trzy sposoby:
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

`bosses.json` przechowuje wyniki walk z bossami (również zapisywany atomowo, uszkodzony plik trafia do `bosses.json.uszkodzony`):

```json
{
  "Smelter Demon": { "deaths": 7, "total_time_seconds": 758, "status": "POKONANO" },
  "Boss 2": { "deaths": 3, "total_time_seconds": 141, "status": "W TRAKCIE" }
}
```

## Walka z bossem

Po zaznaczeniu **„Śledź walkę z bossem”** program sam prowadzi walkę:

- pasek zdrowia bossa na ekranie → **Walka**: timer biegnie, nakładka pokazuje bossa, jego śmierci i łączny czas;
- napis śmierci → **Śmierć**: +1 w ogólnym liczniku i u bossa, timer staje (powrót na arenę nie wlicza się do czasu);
- pasek znów widoczny → walka z tym samym bossem trwa dalej;
- komunikat zwycięstwa → **Boss pokonany**: timer staje na stałe, a nakładka wraca do samego `DEATHS: N`.

Nazwę bossa można wpisać w dowolnym momencie (do tego czasu to „Boss 1”, „Boss 2”…). **Zapisz wynik** zapisuje ostateczny wynik ze statusem POKONANO i czyści panel; dopiero potem kolejny pasek oznacza nowego bossa. **Odrzuć** usuwa pomyłkowy wpis. Gdy śmierć i zwycięstwo wypadną prawie jednocześnie albo w trakcie walki zniknie obraz, panel pokazuje ostrzeżenie i czeka na decyzję („Zapisz wynik” albo „Kontynuuj walkę”). Śmierć poza walką liczy się tylko w ogólnym liczniku, a ręczne +1/−1 w trakcie walki poprawia też licznik bossa. Czas walki jest zapisywany co kilka sekund i przy zamknięciu programu; gdy program jest wyłączony, timer nie biegnie.

### Kalibracja walki z bossem

**Kalibracja… → zakładka „Walka z bossem”** (albo przycisk „Kalibracja walki…” w panelu) ma dwie podzakładki. Obraz pobiera się tak samo jak dla napisu śmierci: **Ctrl+Alt+F9** w grze, przechwycenie z opóźnieniem albo zrzut z pliku (np. F12 w Steam).

- **Pasek bossa** – obraz z walki. Zaznacz **lewy koniec paska** (ozdobną ramkę i początek paska), bez nazwy bossa i bez całego paska, bo wypełnienie maleje, gdy boss traci zdrowie. Walka zaczyna się, gdy pasek jest widoczny przez ok. 1 s, a pasek uznaje się za zniknięty po 3 s nieobecności (`config.json`, sekcja `bosses`).
- **Komunikat zwycięstwa** – obraz z komunikatem po pokonaniu bossa. Zaznacz sam napis.

Komunikat zwycięstwa widać tylko kilka sekund, dlatego najwygodniej zrobić zrzut F12 w trakcie walki i w chwili zwycięstwa, a skalibrować oba wzorce później z plików. Wzorce zapisują się jako `boss_bar.png` i `victory.png`.

Po ponownym uruchomieniu wykrywania (Start) napis widoczny na ekranie nie jest liczony od razu – musi najpierw zniknąć, żeby ta sama śmierć nie została policzona dwa razy.

## Raport PDF

Przycisk **Raport PDF…** (na dole okna) zapisuje raport A4 i od razu go otwiera. Raport zawiera łączną liczbę śmierci, liczbę pokonanych bossów, śmierci przy bossach i łączny czas walk, a w tabelach: **pokonanych bossów** (śmierci i czas pokonania) oraz bossów **niepokonanych** (walka w trakcie). Domyślnie plik trafia obok programu jako `DeathCounter_raport_RRRR-MM-DD.pdf`.

## Gra w pełnym ekranie

Wiele gier (np. Dark Souls II) nie ma trybu okna bez ramek, dlatego program jest przygotowany na pełny ekran:

- **Nakładka przez RTSS.** Zwykłe okno „na wierzchu” często nie przebija się przez ekskluzywny pełny ekran DirectX. Dlatego licznik może być wyświetlany przez [RivaTuner Statistics Server](https://www.guru3d.com/download/rtss-rivatuner-statistics-server-download/) (często instalowany razem z MSI Afterburner). Program tylko wpisuje tekst do pamięci współdzielonej RTSS, a w grze rysuje go RTSS. Wymagania:
  - RTSS jest uruchomiony;
  - „Show On-Screen Display” jest włączone;
  - w programie wybrano tryb „Okno + RTSS” albo „Tylko RTSS”.

  Pozycję, kolor i wielkość tekstu ustawia się w RTSS. Uwaga: sam RTSS, podobnie jak nakładki Steam czy Discord, podpina się pod renderowanie gry. Program licznika nie dotyka gry.
- **Automatyczna instalacja i start RTSS.** Jeśli RTSS nie jest zainstalowany, licznik przy pierwszym uruchomieniu zaproponuje instalację przez winget (paczka `Guru3D.RTSS`). Instalator RTSS poprosi wtedy o zgodę administratora. RTSS wymaga uprawnień administratora przy każdym starcie, dlatego licznik raz, za zgodą w oknie UAC, tworzy zadanie Harmonogramu zadań „DeathCounter - RTSS”. Przez to zadanie uruchamia potem RTSS bez pytania. Sam licznik działa bez uprawnień administratora. Funkcję wyłącza opcja „Uruchamiaj RTSS razem z licznikiem”. Zadanie usuniesz poleceniem `schtasks /Delete /TN "DeathCounter - RTSS" /F` w terminalu uruchomionym jako administrator (zadanie ze starszej wersji programu nazywa się „DS2DeathCounter - RTSS”).
- **Nakładka-okno.** Może być widoczna także w pełnym ekranie, jeśli Windows stosuje dla gry optymalizacje pełnego ekranu. We właściwościach pliku `.exe` gry (np. `DarkSoulsII.exe`) → Zgodność opcja „Wyłącz optymalizacje pełnego ekranu” musi być odznaczona. Trzeba to sprawdzić na swoim komputerze.
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
powershell -ExecutionPolicy Bypass -File build.ps1        # testy + dist\DeathCounter.exe
```

| Skrypt | Rola |
|---|---|
| `uruchom.bat` | uruchomienie ze źródeł (przy pierwszym razie woła `setup.ps1`) |
| `setup.ps1` | tworzy `.venv` na Pythonie 3.12+ i instaluje biblioteki (`-Dev`: także narzędzia) |
| `build.ps1` | `setup.ps1 -Dev`, testy, budowa `.exe` |

| Moduł | Rola |
|---|---|
| `deathcounter/storage.py` | `deaths.json`, zapis atomowy |
| `deathcounter/bosses.py` | walka z bossem: maszyna stanów, timer, `bosses.json` (bez Qt, testowalne) |
| `deathcounter/boss_panel.py` | panel „Walka z bossem” |
| `deathcounter/report.py` | raport PDF (QPdfWriter) |
| `deathcounter/config.py` | `config.json`, ścieżki |
| `deathcounter/template.py` | wzorzec napisu i dopasowanie |
| `deathcounter/detector.py` | maszyna stanów detektora, kontrola obrazu (bez Qt, testowalne) |
| `deathcounter/capture.py` | przechwytywanie DXCam |
| `deathcounter/worker.py` | wątek wykrywania |
| `deathcounter/overlay.py` | nakładka-okno (PySide6 + WinAPI) |
| `deathcounter/rtss.py` | tekst w nakładce RTSS (pamięć współdzielona) |
| `deathcounter/rtss_setup.py` | instalacja RTSS (winget) i start bez UAC (Harmonogram zadań) |
| `deathcounter/calibration.py` | okno kalibracji |
| `deathcounter/main_window.py` | okno główne |
| `deathcounter/icon.py` | ikona „DC” (okno i plik `.ico` dla `build.ps1`) |
