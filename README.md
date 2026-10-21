# Death Counter by MK

*English version: [README_EN.md](README_EN.md).*

Lokalna aplikacja Windows, która automatycznie liczy śmierci w grach wyświetlających po śmierci charakterystyczny napis, np. „NIE ŻYJESZ” / „YOU DIED” w serii Dark Souls, Elden Ring czy Sekiro. Program rozpoznaje ten napis na obrazie gry na podstawie wzorca z kalibracji. Działa offline i nie ingeruje w pliki ani pamięć gry.

## Pobranie i uruchomienie

### Sposób 1: gotowy program (zalecany)

1. Pobierz najnowszy [`DeathCounter.exe`](https://github.com/Kacyn1/DeathCounter/releases/latest/download/DeathCounter.exe). Link zawsze prowadzi do najnowszej wersji. Opis zmian i starsze wersje są w [Releases](https://github.com/Kacyn1/DeathCounter/releases).
2. Umieść go w osobnym folderze, np. `C:\Gry\DeathCounter`. Obok programu będą zapisywane `config.json` i folder `games` z danymi każdej gry (licznik, bossowie, wzorce kalibracji).
3. Uruchom dwuklikiem. Python nie jest potrzebny.

Program nie ma podpisu cyfrowego, więc Windows może pokazać „System Windows ochronił ten komputer”. Kliknij wtedy **Więcej informacji → Uruchom mimo to**.

### Sposób 2: ze źródeł (ZIP z GitHuba)

1. Zainstaluj [Pythona](https://www.python.org/downloads/) w wersji 3.12 lub nowszej. Zostaw zaznaczoną opcję „py launcher”.
2. Pobierz repozytorium (**Code → Download ZIP**) i rozpakuj je. Najlepiej w krótkiej ścieżce, np. `C:\DeathCounter`.
3. Uruchom dwuklikiem **`uruchom.bat`**. Za pierwszym razem skrypt utworzy środowisko `.venv` i pobierze biblioteki (ok. 400 MB, zwykle kilkadziesiąt sekund). Kolejne uruchomienia otwierają program od razu.

Z tego samego folderu możesz zbudować własny `.exe`: `powershell -ExecutionPolicy Bypass -File build.ps1` (wynik w `dist\DeathCounter.exe`).

Jeśli folderu programu nie da się zapisywać, dane trafiają do `%APPDATA%\DeathCounter`.

### Aktualizacje

Program raz dziennie sprawdza na GitHubie, czy jest nowsza wersja. Wysyła wtedy tylko jedno zapytanie o najnowsze wydanie. Gdy nowa wersja jest dostępna, pod licznikiem pojawia się pasek „Dostępna nowa wersja”:
- **Co nowego** – otwiera opis zmian;
- **Aktualizuj** – pobiera nowy `DeathCounter.exe`, sprawdza jego sumę kontrolną SHA-256 podaną przez GitHub, podmienia program i uruchamia go ponownie. Licznik, bossowie, kalibracja i certyfikaty zostają bez zmian. Gdy trwa walka z bossem, program najpierw pyta o zgodę, a czas walki zapisuje przed restartem;
- **Później** – ukrywa pasek do następnego uruchomienia.

Nic nie instaluje się bez kliknięcia „Aktualizuj”. Stara wersja zostaje na chwilę jako `DeathCounter.old.exe` i znika przy kolejnym starcie. W oknie **O programie** można sprawdzić aktualizacje od razu albo wyłączyć codzienne sprawdzanie. W wersji uruchomionej ze źródeł przycisk „Aktualizuj” jest nieaktywny, bo tam aktualizuje się przez `git pull`.

Program działa w jednej kopii. Ponowne kliknięcie ikony, gdy jest już otwarty, wyciąga jego okno na wierzch i sprawdza, czy jest aktualizacja.

## Język programu

Program działa po polsku albo po angielsku. Język zmienisz w oknie **O programie** → lista **Język** (PL / ENG) w prawym górnym rogu. Wybór zapisuje się w `config.json` (`language`), a program uruchamia się ponownie w nowym języku. Przy pierwszym uruchomieniu język dobiera się do języka Windows.

Język dotyczy całego interfejsu, certyfikatu PDF i nazw bossów. Po zmianie języka program raz tłumaczy zapisane nazwy bossów na nazwy z listy gry w nowym języku (np. „Margit, Upadły Omen” → „Margit, the Fell Omen”), razem ze śmierciami, czasem i historią prób. Język gry nie musi zgadzać się z językiem programu, bo odczyt nazwy rozpoznaje nazwy z obu języków.

## Wybór gry

Lista **Gra** nad licznikiem: Dark Souls I, Dark Souls II, Dark Souls III, Sekiro: Shadows Die Twice, Elden Ring. Każda gra ma **osobny** licznik śmierci, bossów i kalibrację (wzorce zapisują się automatycznie dla wybranej gry), a raport PDF ma nazwę gry w tytule. Zmiana gry przy włączonym wykrywaniu zatrzymuje je, wczytuje dane i wzorce tej gry i uruchamia wykrywanie ponownie. Ustawienia programu (nakładka, RTSS, progi, monitor) są wspólne.

Grę spoza listy dodasz pozycją **+ Dodaj grę…** na końcu listy: po podaniu nazwy program tworzy dla niej nowy licznik (z bossami i kalibracją) i od razu ją wybiera. Dodane gry zapisują się w `config.json` (`custom_games`), a ich dane w `games\<nazwa-gry>\`, np. `games\lies-of-p\`.

Przycisk obok listy przenosi dane wybranej gry do **Kosza** (po potwierdzeniu Tak/Nie), skąd można je przywrócić:
- **Usuń licznik** przy grze dodanej przez użytkownika – gra znika z listy razem z licznikiem, bossami i kalibracją, a program przechodzi na Dark Souls I;
- **Resetuj licznik** przy grze wbudowanej (FromSoftware) – takich gier nie można usunąć z listy. Reset zeruje licznik śmierci i listę bossów, a kalibracja się nie zmienia.

### Gry ze Steama

Pozycja **Znajdź zainstalowane gry ze Steam…** na liście gier dodaje liczniki dla gier souls-like zainstalowanych w Steam:

1. Program czyta listę zainstalowanych gier z plików Steama na tym komputerze (`steamapps\libraryfolders.vdf` i `appmanifest_*.acf`), ze wszystkich bibliotek, także na innych dyskach. Logowanie do Steama ani klucz API nie są potrzebne.
2. Pyta sklep Steam o tagi tych gier. Do sklepu trafiają tylko numery gier (AppID), jednym zapytaniem. Tag „Souls-like” mają też gry tylko inspirowane soulsami, dlatego liczy się jego miejsce wśród tagów gry (Steam układa je od najczęściej nadawanego):
   - **souls-like** (zaznaczone) – tag wśród 3 głównych tagów albo gra z wbudowanej listy znanych souls-like (np. Nioh 2 i Black Myth: Wukong mają tag dopiero na 4. miejscu);
   - **możliwe souls-like** (osobna sekcja, niezaznaczone) – tag na miejscach 4–10, np. Armored Core VI czy Dead Cells. Zaznacz grę, jeśli ma ekran śmierci;
   - gry z tagiem dalej albo bez tagu nie są pokazywane.
3. **Dodaj zaznaczone** tworzy dla zaznaczonych gier liczniki, tak jak „+ Dodaj grę…”.

Gry wbudowane (także Dark Souls: Remastered i Scholar of the First Sin) są rozpoznawane po AppID i pokazane jako „wbudowane w program”. Gry dodane wcześniej są pomijane – numer AppID zapisuje się w `config.json` (`steam_appids`). Gdy sklep Steam nie odpowiada, program korzysta z wbudowanej listy znanych gier souls-like. Dodana gra wymaga kalibracji, jak każda gra spoza listy.

Przy pierwszym uruchomieniu na komputerze ze Steamem program raz proponuje takie wyszukanie.

Dane gry leżą w `games\<gra>\` obok programu (`ds1`, `ds2`, `ds3`, `sekiro`, `eldenring`): `deaths.json`, `bosses.json`, `calibration.json` i pliki wzorców. Po aktualizacji z wersji bez wyboru gry program jednorazowo pyta, do której gry przypisać dotychczasowy licznik, bossów i kalibrację, i przenosi je do jej folderu.

## Pierwsze użycie: kalibracja

1. Uruchom grę (pełny ekran lub okno).
2. Kliknij **Kalibracja…** i pobierz obraz z napisem po śmierci (np. „NIE ŻYJESZ”). Masz trzy sposoby:
   - w trakcie ekranu śmierci naciśnij **Ctrl+Alt+F9** (usłyszysz sygnał), a potem otwórz kalibrację;
   - ustaw opóźnienie i kliknij **Przechwyć ekran**;
   - wczytaj zrzut ekranu z gry (np. F12 w Steam).
3. Zaznacz myszą prostokąt obejmujący sam napis i kliknij **Sprawdź wzorzec**. Wynik powinien przekroczyć próg.
4. Kliknij **Zapisz wzorzec**, a potem **Start**.

Wzorzec warto też sprawdzić na zwykłym zrzucie z rozgrywki. Wynik powinien być tam wyraźnie niższy od progu.

Po zapisaniu wzorca okno kalibracji przy kolejnym otwarciu pokazuje w każdej zakładce zrzut, z którego go wycięto, wraz z zaznaczonym obszarem (przycisk **Pokaż zapisany wzorzec** wraca do niego po wczytaniu innego obrazu). Zrzuty leżą w folderze gry obok wzorców jako `template_source.jpg`, `boss_bar_source.jpg` i `victory_source.jpg`. Wzorce zapisane w wersji 1.2.0 i starszych nie mają zrzutu – widać wtedy sam wzorzec na czarnym tle, a po ponownym zapisaniu pojawi się cały obraz. Przycisk **Zrzut ze skrótu** wstawia ostatni zrzut zrobiony skrótem Ctrl+Alt+F9.

## Jak działa wykrywanie

- Co ok. 0,1 s pobierana jest klatka (DXCam). Okolica miejsca napisu jest porównywana ze wzorcem (OpenCV, `TM_CCOEFF_NORMED`). Wzorzec skaluje się automatycznie do bieżącej rozdzielczości.
- **Potwierdzanie:** śmierć liczy się dopiero wtedy, gdy napis jest widoczny na 3 kolejnych próbkach.
- **Brak duplikatów:** po zliczeniu detektor czeka, aż napis zniknie na co najmniej 3 s. Między dwiema śmierciami musi też minąć co najmniej 8 s.
- **Błędy obrazu:** brak nowych klatek, zamrożony obraz (ponad 5 s) i zmiana rozdzielczości są sygnalizowane w oknie. W tym czasie nic nie jest liczone.

Sekcje „Nakładka” i „Wykrywanie” zwija i rozwija kliknięcie w ich tytuł. Stan jest zapamiętywany. Progi, liczbę próbek potwierdzenia, czas ponownego uzbrojenia i monitor ustawisz w oknie. Są dwa progi dopasowania: **„Próg śmierci i zwycięstwa”** dotyczy napisu śmierci i komunikatu zwycięstwa (oba to duże napisy na środku ekranu), a **„Próg paska bossa”** – wzorca paska zdrowia bossa. Pozostałe parametry są w `config.json` (sekcja `detector`).

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

Nazwę bossa można wpisać w dowolnym momencie (do tego czasu to „Boss 1”, „Boss 2”…), ale zwykle nie trzeba – patrz niżej. **Zapisz wynik** zapisuje ostateczny wynik ze statusem POKONANO i czyści panel; dopiero potem kolejny pasek oznacza nowego bossa. **Odrzuć** usuwa pomyłkowy wpis. Gdy śmierć i zwycięstwo wypadną prawie jednocześnie albo w trakcie walki zniknie obraz, panel pokazuje ostrzeżenie i czeka na decyzję („Zapisz wynik” albo „Kontynuuj walkę”). Śmierć poza walką liczy się tylko w ogólnym liczniku, a ręczne +1/−1 w trakcie walki poprawia też licznik bossa. Czas walki jest zapisywany co kilka sekund i przy zamknięciu programu; gdy program jest wyłączony, timer nie biegnie.

**Opuszczenie areny.** Gdy pasek zniknie, a przez kolejne 15 s nie pojawi się ani napis śmierci, ani komunikat zwycięstwa, program uznaje, że wyszedłeś z areny. Walka zostaje przerwana, a panel pokazuje „Walka przerwana (opuszczono arenę): …”. Licząc od zniknięcia paska, trwa to ok. 18 s, bo samo zniknięcie paska jest potwierdzane po 3 s. Boss zostaje w `bosses.json` jako „W TRAKCIE”, ze wszystkimi śmierciami i czasem. Gdy wrócisz na arenę, odczyt nazwy podłączy walkę z powrotem do tego bossa. Funkcja działa tylko przy skalibrowanym komunikacie zwycięstwa, bo bez niego nie da się odróżnić wygranej od ucieczki.

**Ostatnie walki.** Pod bieżącą walką panel pokazuje 3 ostatnie walki z ich wynikiem: W TRAKCIE, PRZERWANO albo POKONANO, z liczbą śmierci, czasem i chwilą ostatniej zmiany. Lista jest zapisywana w `recent_fights.json` w folderze gry i przetrwa ponowne uruchomienie. Przy walce niezakończonej są dwa przyciski:
- **Pokonany** – gdy to była wygrana, której program nie wykrył;
- **Usuń** – gdy to był fałszywy start, np. przebiegnięcie obok bossa w otwartym świecie. Usuwa bossa razem z wynikiem.

Przycisk **Wyniki…** w panelu walki otwiera osobne okno z tabelą wszystkich bossów wybranej gry: nazwa, status (bieżąca walka, w trakcie, pokonany), liczba śmierci i czas. Nad tabelą jest podsumowanie: śmierci łącznie, pokonani bossowie, śmierci przy bossach i łączny czas walk. Okno nie blokuje programu i odświeża się co sekundę, a kliknięcie nagłówka kolumny zmienia sortowanie.

**Historia prób.** Dwuklik w bossa w oknie „Wyniki” rozwija pod nim listę jego prób, od najnowszej. Widać 15 wierszy, a starsze próby są dostępne po przewinięciu. Każda próba ma numer, godzinę rozpoczęcia, czas walki i wynik:
- Śmierć albo Śmierć (ręcznie),
- Zwycięstwo,
- Przerwano (opuszczono arenę),
- Przerwano (zatrzymano wykrywanie),
- Cofnięto (−1),
- W toku – dla trwającej próby, z czasem na żywo.

Nad listą jest podsumowanie: liczba prób, średni i najdłuższy czas oraz numer próby, w której boss został pokonany.

Próba trwa od pojawienia się paska do śmierci, zwycięstwa albo przerwania. Pasek, który zniknie na chwilę i wróci bez śmierci (np. przerywnik między fazami), to wciąż ta sama próba. Historia zapisuje się w `attempts.json` w folderze gry i zbiera się od wersji 1.8.0.

### Odczyt nazwy bossa

Gdy opcja **„Odczytuj nazwę bossa z ekranu”** jest włączona (domyślnie tak), program chwilę po pojawieniu się paska czyta nazwę wypisaną nad nim. Używa wbudowanego w Windows rozpoznawania tekstu (OCR), z polskim albo angielskim pakietem językowym – tym, który jest zainstalowany (najpierw w języku programu). Działa to bez internetu i niczego nie wysyła. Jeśli w Windows nie ma żadnego z tych pakietów, program napisze, gdzie go dodać.

- **Wbudowane listy nazw.** Dla Dark Souls I–III, Sekiro i Elden Ringa (z dodatkami) program ma listę nazw bossów z plików gier, w parach polska–angielska (`deathcounter/data/boss_names/`). Odczyt dostaje najbardziej podobną nazwę z listy wybranej gry, w języku programu – także wtedy, gdy gra jest w innym języku. Kilku nazw polska wersja Dark Souls I nie tłumaczy; na liście mają polskie odpowiedniki („Demon Mędrzec Ognia”, „Wiatraczek”, „Nito, Władca Grobów”, „Seath Bezłuski”), a tekst z gry jest rozpoznawany.
- **Podobieństwo nazwy bossa** (sekcja „Wykrywanie”, domyślnie 0,60) określa, jak bardzo odczyt może różnić się od znanej nazwy. Niżej – więcej poprawionych błędów OCR, ale boss spoza listy łatwiej dostaje cudzą nazwę.
- **Poprawianie zapisanych nazw.** Przy pierwszym wczytaniu gry z nową listą (albo po zmianie języka) program raz porównuje zapisane nazwy bossów z listą i poprawia podobne, a potem pokazuje, co zmienił. To samo robi na żądanie przycisk **Popraw nazwy bossów** w oknie „Wyniki” – najpierw pokazuje zmiany i czeka na potwierdzenie.

- Program uczy się nazw. Nazwa zatwierdzona przyciskiem „Zapisz wynik” albo wpisana ręcznie trafia do `boss_names.json` w folderze gry. Kolejne odczyty są dopasowywane do znanych nazw, więc pomyłka OCR w jednej literze nie tworzy nowego bossa.
- Jeśli poprawisz źle odczytaną nazwę, program zapamięta ten błędny odczyt. Przy następnej walce od razu da poprawną nazwę.
- Powrót po śmierci do tego samego bossa łączy podejścia. Jeśli wpiszesz krótszą nazwę (np. „Margit”), też zostanie uznana za tego samego bossa.
- Gdy pasek pojawi się przy innym bossie niż ostatni niepokonany, walka przechodzi na nowego bossa razem z czasem od pojawienia się paska. Poprzedni zostaje w pliku jako „W TRAKCIE”.

**Automatyczny zapis wyniku.** Program zapisuje wynik sam, ok. 4 s po potwierdzonym komunikacie zwycięstwa, i pokazuje w panelu „Automatycznie zapisany: …”. Robi to tylko wtedy, gdy nazwa bossa jest pewna, czyli:
- większość prób OCR dała ten sam tekst,
- albo odczyt pasuje do znanej nazwy,
- albo nazwę wpisałeś ręcznie.

Dodatkowo nic nie może budzić wątpliwości: śmierć tuż przed albo tuż po zwycięstwie czy utrata obrazu blokują zapis. Gdy nazwa jest niepewna, panel prosi o jej sprawdzenie i kliknięcie **Zapisz wynik**. Taka nazwa jest potem znana, więc następna walka z tym bossem zapisze się już sama.

Nazwa jest szukana w pasie nad paskiem, od miejsca znalezionego wzorca na ok. 1/3 szerokości ekranu w lewo. Dlatego działa bez względu na to, który fragment paska zaznaczysz w kalibracji. Odczyty trafiają do `diagnostyka.log`.

### Kalibracja walki z bossem

**Kalibracja… → zakładka „Walka z bossem”** (albo przycisk „Kalibracja walki…” w panelu) ma dwie podzakładki. Obraz pobiera się tak samo jak dla napisu śmierci: **Ctrl+Alt+F9** w grze, przechwycenie z opóźnieniem albo zrzut z pliku (np. F12 w Steam).

- **Pasek bossa** – obraz z walki. Zaznacz **lewy koniec paska** (ozdobną ramkę i początek paska), bez nazwy bossa i bez całego paska, bo wypełnienie maleje, gdy boss traci zdrowie. Walka zaczyna się, gdy pasek jest widoczny przez ok. 1 s, a pasek uznaje się za zniknięty po 3 s nieobecności (`config.json`, sekcja `bosses`).
- **Komunikat zwycięstwa** – obraz z komunikatem po pokonaniu bossa. Zaznacz sam napis.

Komunikat zwycięstwa widać tylko kilka sekund, dlatego najwygodniej zrobić zrzut F12 w trakcie walki i w chwili zwycięstwa, a skalibrować oba wzorce później z plików. Wzorce zapisują się jako `boss_bar.png` i `victory.png`.

Po ponownym uruchomieniu wykrywania (Start) napis widoczny na ekranie nie jest liczony od razu – musi najpierw zniknąć, żeby ta sama śmierć nie została policzona dwa razy.

## Aktualna sesja

Sekcja **Aktualna sesja** (pod „Walką z bossem”) pokazuje śmierci i czas bieżącej sesji gry:

- sesja zaczyna się, gdy uruchomisz grę, a czas biegnie tylko wtedy, gdy gra jest włączona. Program co 2 s sprawdza listę procesów Windows – tylko ją odczytuje, gry nie dotyka;
- czas biegnie tylko wtedy, gdy gra jest aktywnym oknem. Gdy ją zminimalizujesz, przejdziesz Alt+Tab do innego okna (także z okna bez ramek), klikniesz w inny program albo zablokujesz ekran – czas sesji stoi. Po powrocie do gry program sprawdza jeszcze raz po ok. 2 s, czy gra nadal jest aktywna – jeśli tak, czas rusza, a te 2 s są doliczone. Kliknięcie w okno samego licznika też chwilowo zatrzymuje czas (nakładki to nie dotyczy);
- powrót do gry w ciągu 15 minut (np. po wysypaniu się gry albo wyjściu do pulpitu) kontynuuje tę samą sesję, a czas przerwy się nie liczy. Po dłuższej przerwie uruchomienie gry zaczyna nową sesję;
- do sesji liczą się śmierci wykryte i ręczne +1/−1, gdy gra jest uruchomiona; reset licznika zeruje też sesję;
- sesja jest osobna dla każdej gry i zapisuje się w `session.json` w folderze gry, więc ponowne uruchomienie programu (np. po aktualizacji) jej nie przerywa.

Opcje w sekcji:
- **Śledź sesję** – włącza i wyłącza całą funkcję;
- **Przełączaj licznik na uruchomioną grę** – gdy uruchomisz inną grę z listy, licznik sam się na nią przełączy i napisze o tym w oknie. Jeśli ta gra nie ma jeszcze kalibracji, program o tym przypomni i zamiga na pasku zadań. Przełączenie następuje tylko w chwili uruchomienia gry – gdy w trakcie grania sam wybierzesz inną grę, program tego nie cofa;
- **Pokaż sesję na nakładce** – nakładka i RTSS pokazują dodatkową linię „Sesja: 12 · 01:40:12”.

Stan sesji pokazuje znacznik: **W GRZE** (czas biegnie), **PAUZA** (gra w tle), **PRZERWA** (gra zamknięta, powrót w ciągu 15 min kontynuuje sesję), **OCZEKIWANIE**, **NIEZNANA GRA** (wskaż exe) albo **WYŁĄCZONA**. Status na Discordzie pokazuje czas od początku sesji.

**Statystyki sesji…** (przycisk w sekcji) otwiera okno, które nie blokuje programu i odświeża się co sekundę. Ma dwie zakładki:
- **Aktualna sesja** – kafelki (śmierci, czas gry, śmierci na godzinę, najdłużej bez śmierci, od ostatniej śmierci) i wykres liniowy: łączna liczba śmierci w czasie gry. Każda śmierć to skok linii o 1, więc strome fragmenty pokazują, gdzie była „ściana” (np. boss). Oś czasu to czas gry w sesji, bez pauz. Po najechaniu myszą widać czas gry i liczbę śmierci w tej chwili;
- **Wszystkie sesje** – kafelki (liczba sesji, śmierci i czas gry łącznie, średnio na sesję, śmierci na godzinę), wykres słupkowy śmierci w kolejnych sesjach (ostatnich 20; po najechaniu – data, czas gry i śmierci na godzinę) i tabela wszystkich sesji, od najnowszej.

Zakończone sesje zapisują się w `session_history.json` w folderze gry (bez sesji krótszych niż minuta i bez śmierci), a czas każdej śmierci – w `session.json`. Historia i czasy śmierci zbierają się od wersji 1.12.0. „Resetuj licznik” czyści też historię sesji danej gry.

Jak program rozpoznaje grę: gry wbudowane po nazwie exe (`DARKSOULS.exe`, `DarkSoulsRemastered.exe`, `DarkSoulsII.exe`, `DarkSoulsIII.exe`, `sekiro.exe`, `eldenring.exe`), gry ze Steama po folderze instalacji (dowolny exe z `steamapps\common\<gra>`), a gry dodane ręcznie – po nazwie zainstalowanej gry Steam. Dla gry spoza Steama (np. GOG, Epic) w sekcji pojawia się przycisk **Wskaż exe gry…**; wybrany plik zapisuje się w `config.json` (`game_exes`).

## Certyfikat PDF

Przycisk **Certyfikat PDF…** (na dole okna) zapisuje certyfikat wybranej gry (A4 poziomo) i od razu go otwiera: logo, nick gracza (program pyta o niego i zapamiętuje), gra, śmierci łącznie, liczba pokonanych bossów, śmierci przy bossach i czas ich pokonania oraz lista pokonanych bossów. Gdy bossów jest więcej, pełna lista (także walki w trakcie) trafia do załącznika na kolejnych stronach.

Zabezpieczenia przed podrobieniem:
- **kod weryfikacyjny** na certyfikacie – podpis HMAC-SHA256 danych certyfikatu tajnym kluczem,
- podpisane dane ukryte w metadanych pliku (XMP),
- **niewidoczny znak wodny** – mikrotekst z kodem, grą, nickiem i liczbą śmierci, w kolorze prawie identycznym z tłem (widać go dopiero po powiększeniu i podbiciu kontrastu).

**Ręczne zmiany wyniku.** Każda gra ma podpisany rejestr zmian (`audit.json`). Program zapisuje w nim ręczne korekty (przyciski i skróty +1/−1, reset, +1/−1 przy bossie) oraz wykrywa zmiany plików z wynikami poza programem (np. edycję `deaths.json` lub czasu bossa w `bosses.json`). Jeśli wynik był zmieniany, certyfikat ma czerwoną adnotację, a załącznik „Korekty” pokazuje, ile dodano lub odjęto ręcznie i co zmieniono poza programem. Edycja rejestru zostaje wykryta, a jego usunięcie oznacza istniejące wyniki jako „bez historii zmian”. Bez zmian certyfikat wygląda zwyczajnie.

Przycisk **Sprawdź certyfikat…** wczytuje PDF i mówi, czy jest prawdziwy, a także pokazuje podpisane dane – jeśli ktoś zmienił liczby na certyfikacie, widać różnicę. Klucz (`deathcounter\_signing_key.py`) nie trafia do repozytorium: `build.ps1` tworzy go przy pierwszym budowaniu i dołącza do exe. Certyfikaty z wersji uruchomionej ze źródeł (bez klucza) są oznaczone jako niepodpisane. Kod jest publiczny, a klucz da się wydobyć z exe, więc podpis bardzo utrudnia podrabianie, ale go nie wyklucza.

## Status na Discordzie

Opcja **Status na Discordzie** (sekcja „Nakładka”) pokazuje w Twoim statusie Discord wybraną grę, liczbę śmierci i czas od rozpoczęcia sesji. Program rozmawia tylko z aplikacją Discord uruchomioną na tym komputerze (lokalny kanał Rich Presence) i sam łączy się ponownie, gdy Discord zostanie włączony później. Wyłączenie opcji lub zamknięcie programu czyści status.

Do działania potrzebny jest identyfikator aplikacji z [Discord Developer Portal](https://discord.com/developers/applications) (nazwa tej aplikacji pojawia się w statusie jako „Gra w …”). Własny identyfikator można wpisać w `config.json` → `discord` → `client_id`.

## Gra w pełnym ekranie

Wiele gier (np. Dark Souls II) nie ma trybu okna bez ramek, dlatego program jest przygotowany na pełny ekran:

- **Czy licznik widać w grze?** Przycisk **Pokaż nakładkę / Ukryj nakładkę** włącza i wyłącza nakładkę, a wiersz **Nakładka** w sekcji „Stan” mówi, czy licznik jest widoczny: **WIDOCZNA**, **CZĘŚCIOWO** (okno widoczne, ale RTSS nie działa – w pełnym ekranie licznika może nie być widać), **NIEWIDOCZNA** (tryb „Tylko RTSS”, a RTSS nie działa) albo **UKRYTA** (nakładka wyłączona). Obok jest podpowiedź, co zrobić.

- **Nakładka przez RTSS.** Zwykłe okno „na wierzchu” często nie przebija się przez ekskluzywny pełny ekran DirectX. Dlatego licznik może być wyświetlany przez [RivaTuner Statistics Server](https://www.guru3d.com/download/rtss-rivatuner-statistics-server-download/) (często instalowany razem z MSI Afterburner). Program tylko wpisuje tekst do pamięci współdzielonej RTSS, a w grze rysuje go RTSS. Wymagania:
  - RTSS jest uruchomiony;
  - „Show On-Screen Display” jest włączone;
  - w programie wybrano tryb „Okno + RTSS” albo „Tylko RTSS”.

  Pozycję, kolor i wielkość tekstu ustawia się w RTSS. Uwaga: sam RTSS, podobnie jak nakładki Steam czy Discord, podpina się pod renderowanie gry. Program licznika nie dotyka gry.
- **Automatyczna instalacja i start RTSS.** Jeśli RTSS nie jest zainstalowany, licznik przy pierwszym uruchomieniu zaproponuje instalację przez winget (paczka `Guru3D.RTSS`). Instalator RTSS poprosi wtedy o zgodę administratora. RTSS wymaga uprawnień administratora przy każdym starcie, dlatego licznik raz, za zgodą w oknie UAC, tworzy zadanie Harmonogramu zadań „DeathCounter - RTSS”. Przez to zadanie uruchamia potem RTSS bez pytania. Sam licznik działa bez uprawnień administratora. Funkcję wyłącza opcja „Uruchamiaj RTSS razem z licznikiem”. Zadanie usuniesz poleceniem `schtasks /Delete /TN "DeathCounter - RTSS" /F` w terminalu uruchomionym jako administrator (zadanie ze starszej wersji programu nazywa się „DS2DeathCounter - RTSS”).
- **Nakładka-okno.** Może być widoczna także w pełnym ekranie, jeśli Windows stosuje dla gry optymalizacje pełnego ekranu. We właściwościach pliku `.exe` gry (np. `DarkSoulsII.exe`) → Zgodność opcja „Wyłącz optymalizacje pełnego ekranu” musi być odznaczona. Trzeba to sprawdzić na swoim komputerze.
- **Skróty globalne**, bez wychodzenia z gry (domyślnie):
  - **Ctrl+Alt+F9** – zrzut do kalibracji;
  - **Ctrl+Alt+F10** – +1;
  - **Ctrl+Alt+F11** – −1;
  - **Ctrl+Alt+F8** – włączenie/wyłączenie nakładki.

  Każdy skrót potwierdza sygnał dźwiękowy. Przycisk **„Skróty…”** pozwala zmienić każdy skrót (kliknij pole i naciśnij nową kombinację), wyłączyć go przyciskiem ✕ albo przywrócić domyślne. Litery, cyfry i spacja wymagają Ctrl, Alt albo Win, żeby nie blokować pisania.
- **Automatyczny start.** Opcja „Włączaj wykrywanie przy starcie” pozwala uruchomić licznik przed grą i nie przełączać się do jego okna.
- **Przechwytywanie obrazu** (DXGI Desktop Duplication) działa w pełnym ekranie. Gdy gra zmienia tryb ekranu albo rozdzielczość, przechwytywanie jest odtwarzane automatycznie, a wzorzec przeskalowany.

## Zgłaszanie błędów: plik diagnostyczny

Obok programu powstaje `diagnostyka.log` (najwyżej ok. 2 MB, starsza część trafia do `diagnostyka.log.1`). Zapisuje przebieg wykrywania: start i stop, każdą wykrytą śmierć (licznik ogólny i bossa przed i po), przejścia detektora („gotowy” / „czeka na zniknięcie napisu”), zdarzenia walki z bossem, zmiany stanu i co 5 s wyniki dopasowania wzorców. Nie zawiera obrazów. Przy zgłaszaniu błędu dołącz ten plik i napisz, o której godzinie wystąpił problem.

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
| `deathcounter/results_window.py` | okno „Wyniki” z tabelą bossów |
| `deathcounter/updater.py` | aktualizacja z GitHuba (sprawdzenie, pobranie, podmiana exe) |
| `deathcounter/attempts.py` | historia pojedynczych prób (`attempts.json`) |
| `deathcounter/recent_fights.py` | ostatnie walki w panelu (`recent_fights.json`) |
| `deathcounter/collapsible.py` | zwijane sekcje okna („Nakładka”, „Wykrywanie”) |
| `deathcounter/ocr.py` | odczyt nazwy bossa (OCR Windows) |
| `deathcounter/boss_names.py` | znane nazwy bossów gry i dopasowanie odczytu (`boss_names.json`, listy z `data/boss_names/`) |
| `deathcounter/i18n.py`, `deathcounter/lang_en.py` | język interfejsu: `tr("polski tekst")` i tłumaczenie angielskie |
| `deathcounter/report.py` | certyfikat PDF (QPdfWriter), weryfikacja |
| `deathcounter/audit.py` | rejestr ręcznych korekt i zmian poza programem (`audit.json`) |
| `deathcounter/diagnostics.py` | plik diagnostyczny `diagnostyka.log` |
| `deathcounter/legal.py` | licencja (GNU GPL v3) i licencje bibliotek, okno „O programie” |
| `deathcounter/signing.py` | kod weryfikacyjny certyfikatu (HMAC), klucz spoza repozytorium |
| `deathcounter/discord_presence.py` | status na Discordzie (Rich Presence przez lokalny kanał Discorda) |
| `deathcounter/config.py` | `config.json`, lista gier, ścieżki, `calibration.json`, przeniesienie starych danych |
| `deathcounter/play_session.py` | aktualna sesja: śmierci i czas przy uruchomionej grze (`session.json`), historia sesji (`session_history.json`) |
| `deathcounter/session_stats.py` | okno „Statystyki sesji” z wykresami |
| `deathcounter/game_process.py` | która gra jest uruchomiona (procesy Windows dopasowane do gier) |
| `deathcounter/steam_library.py` | gry z biblioteki Steam i rozpoznanie souls-like (tagi sklepu, lista zapasowa) |
| `deathcounter/steam_dialog.py` | okno „Znajdź zainstalowane gry ze Steam” |
| `deathcounter/game_data.py` | wczytanie danych jednej gry (licznik, bossowie, wzorce) |
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

## Licencja

Copyright (C) 2026 Mateusz Kacyna

Ten program jest wolnym oprogramowaniem: możesz go rozpowszechniać i/lub modyfikować na warunkach Powszechnej Licencji Publicznej GNU w wersji 3 ([GNU GPL v3](LICENSE), GPL-3.0-only), opublikowanej przez Free Software Foundation. Program jest rozpowszechniany w nadziei, że będzie przydatny, ale **bez jakiejkolwiek gwarancji** – szczegóły w treści licencji.

W skrócie: każdy może używać programu, przeglądać i zmieniać kod oraz rozpowszechniać go dalej, ale zmienione wersje muszą być również udostępniane na GPL v3 razem z kodem źródłowym.

**Certyfikaty.** Klucz podpisu certyfikatów nie jest częścią kodu źródłowego. Program zbudowany z kodu (`build.ps1`) tworzy własny klucz, więc jego certyfikaty nie przejdą weryfikacji w oficjalnych wydaniach z [Releases](https://github.com/Kacyn1/DeathCounter/releases) – i odwrotnie. Dzięki temu „Sprawdź certyfikat…” potwierdza tylko certyfikaty z oficjalnego programu.

Program korzysta z bibliotek osób trzecich na ich własnych licencjach – Qt for Python (LGPL v3), OpenCV (Apache 2.0), NumPy (BSD), DXcam, comtypes i PyWinRT (MIT) oraz Pythona (PSF); pełne teksty są w [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt) i w oknie **O programie**. Po aktualizacji bibliotek listę licencji odświeża `tools\make_third_party_licenses.py`.

Propozycje zmian: [CONTRIBUTING.md](CONTRIBUTING.md).
