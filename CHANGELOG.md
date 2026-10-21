# Historia zmian

## 1.11.0

- Nowa sekcja „Aktualna sesja” pod „Walką z bossem”: śmierci i czas bieżącej sesji. Sesja zaczyna się, gdy uruchomisz grę – program co 2 s sprawdza listę procesów Windows (tylko odczyt, gra nie jest w żaden sposób dotykana). Czas biegnie tylko wtedy, gdy gra jest aktywnym oknem – stoi, gdy gra jest zminimalizowana, w tle po Alt+Tab (także w oknie bez ramek) albo ekran jest zablokowany. Po powrocie do gry rusza, gdy kolejne sprawdzenie po ok. 2 s potwierdzi, że gra nadal jest aktywna, i te 2 s są doliczane. Powrót do gry w ciągu 15 minut (np. po wysypaniu się gry) kontynuuje tę samą sesję, a czas przerwy się nie liczy. Sesja jest osobna dla każdej gry, zapisuje się w `session.json` w folderze gry i przetrwa ponowne uruchomienie programu. Śledzenie można wyłączyć polem „Śledź sesję”.
- Opcja „Pokaż sesję na nakładce” dodaje do nakładki i RTSS linię „Sesja: 12 · 01:40:12”. Status na Discordzie pokazuje czas od początku sesji.
- Licznik sam przełącza się na grę, którą uruchomisz (opcja „Przełączaj licznik na uruchomioną grę”, domyślnie włączona). Gdy ta gra nie ma jeszcze kalibracji, program o tym informuje i miga na pasku zadań. Przełączenie następuje tylko w chwili uruchomienia gry, więc ręczny wybór innej gry w trakcie grania zostaje.
- Gry wbudowane program rozpoznaje po nazwie exe, gry ze Steama – po folderze instalacji, a gry dodane ręcznie – po nazwie zainstalowanej gry Steam. Dla gier spoza Steama (np. GOG, Epic) jest przycisk „Wskaż exe gry…”.
- Nowa pozycja na liście gier: „Znajdź zainstalowane gry ze Steam…”. Program czyta z plików Steama na tym komputerze listę zainstalowanych gier (ze wszystkich bibliotek, także na innych dyskach) i sprawdza w sklepie Steam, które z nich mają tag „Souls-like”. Znalezione gry pokazuje do zaznaczenia, a po kliknięciu „Dodaj zaznaczone” tworzy dla nich liczniki. Nie trzeba logować się do Steama ani podawać klucza API. Do sklepu trafiają tylko numery gier (AppID).
- Gry z tagiem wśród 3 głównych tagów (albo z wbudowanej listy) są zaznaczone. Gry z tagiem na miejscach 4–10 trafiają do osobnej, niezaznaczonej sekcji „Możliwe souls-like” – to zwykle gry tylko inspirowane soulsami, np. Armored Core VI czy Dead Cells. Gry z tagiem dalej nie są pokazywane.
- Bez internetu program korzysta z wbudowanej listy 25 znanych gier souls-like (m.in. Lies of P, Nioh 1–2, Lords of the Fallen, Remnant 1–2, Hollow Knight, Black Myth: Wukong).
- Gry wbudowane w program (Dark Souls I–III, Sekiro, Elden Ring) są rozpoznawane po AppID i nie są dodawane drugi raz. Gry dodane wcześniej ze Steama albo o tej samej nazwie też są pomijane.
- Przy pierwszym uruchomieniu na komputerze ze Steamem program raz proponuje wyszukanie gier.
- Gier FromSoftware nie można usunąć z listy: przy nich przycisk „Usuń licznik” nazywa się teraz „Resetuj licznik”. Zeruje licznik śmierci i bossów (pliki trafiają do Kosza), a kalibracja zostaje.
- Okno programu mieści się na mniejszych ekranach (np. Full HD albo skalowanie 125–150%): ma wysokość ekranu, a zawartość przewija się w pionie. Okno dopasowuje wysokość przy starcie, przy zwijaniu i rozwijaniu sekcji oraz po przeciągnięciu na inny monitor, i nigdy nie wystaje poza ekran. Można je też dowolnie zmniejszyć w pionie.

## 1.10.0

- Program ma angielską wersję językową. Język (PL / ENG) wybiera się w oknie „O programie” – lista „Język” z flagami w prawym górnym rogu; po zmianie program uruchamia się ponownie w nowym języku. Przy pierwszym uruchomieniu język dobiera się do języka Windows, a dotychczasowi użytkownicy zostają przy polskim. Przetłumaczony jest cały interfejs, komunikaty i certyfikat PDF.
- Listy nazw bossów wszystkich pięciu gier mają teraz pary polska–angielska z plików gier. Odczyt nazwy rozpoznaje nazwy w obu językach i podaje je w języku programu, więc język gry nie musi zgadzać się z językiem programu. Po zmianie języka zapisane nazwy bossów są raz tłumaczone razem ze śmierciami, czasem i historią prób.
- Odczyt nazwy bossa nie wymaga już polskiego pakietu OCR Windows – wystarczy polski albo angielski.
- Dane w plikach (statusy „W TRAKCIE” / „POKONANO”, dane podpisane w certyfikacie) zostają w dotychczasowej postaci, więc wyniki i certyfikaty z poprzednich wersji działają bez zmian w obu językach.
- Dodano angielskie README (`README_EN.md`).

## 1.9.36

- Dodano wbudowane listy polskich nazw bossów dla Sekiro (50) i Elden Ringa (181, razem z dodatkiem Shadow of the Erdtree), wyciągnięte z polskiej wersji plików gier. Działają tak samo jak listy Dark Souls: odczyt z ekranu dostaje najbardziej podobną nazwę z listy wybranej gry, przy pierwszym wczytaniu gry zapisane nazwy są raz porównywane z listą, a w oknie „Wyniki” dostępny jest przycisk „Popraw nazwy bossów”.
- Lista Elden Ringa obejmuje bossów głównych, polowych, z lochów i z dodatku oraz bossów-ludzi z paskiem zdrowia, takich jak Esgar, Czempion Fii, Gideon Ofnir czy uczestnicy walki z Ledą. Nie obejmuje kupców ani zwykłych postaci.

## 1.9.35

- Przy wczytaniu Dark Souls I, II lub III program porównuje zapisane wcześniej nazwy bossów z listą nazw gry i poprawia te, które są do niej podobne, na przykład błędne odczyty OCR. Poprawiane są wpisy w `bosses.json`, historia prób, lista ostatnich walk, rejestr zmian oraz nazwy w `boss_names.json`. Dwa wpisy tego samego niepokonanego bossa są scalane, a pokonany boss dostaje numer, tak jak przy ręcznej zmianie nazwy. Stara błędna nazwa zostaje zapamiętana jako alias. Program pokazuje listę zmian i zapisuje ją w `diagnostyka.log`.
- Sprawdzenie odbywa się raz dla każdej wersji listy nazw (znacznik `builtin_checked` w `boss_names.json`), więc nazwa poprawiona później ręcznie nie zostanie zmieniona przy kolejnym uruchomieniu.
- W oknie „Wyniki” dodano przycisk „Popraw nazwy bossów” (dla Dark Souls I–III). Program porównuje nazwy w tabeli z listą nazw gry, pokazuje, które z nich zmieni, i po potwierdzeniu podmienia je w ten sam sposób co przy wczytaniu gry. Można go użyć w dowolnym momencie, na przykład gdy po sprawdzeniu przy starcie pojawi się nowy błędnie odczytany boss.

## 1.9.3

- Dodano wbudowane listy polskich nazw bossów dla Dark Souls I (27), II (47) i III (34, z dodatkami). Nazwy pochodzą z polskiej wersji językowej plików gier. Nazwa odczytana przez OCR jest porównywana z listą aktualnie wybranej gry i zastępowana najbardziej podobną nazwą, tak jak dotąd w przypadku nazw zapamiętanych z walk.
- Polska wersja Dark Souls I nie tłumaczy czterech nazw bossów. Na liście mają polskie odpowiedniki: „Demon Mędrzec Ognia”, „Wiatraczek”, „Nito, Władca Grobów” i „Seath Bezłuski”. Angielskie nazwy wyświetlane przez grę są zapisane jako aliasy, więc odczyt z ekranu nadal daje właściwą nazwę.
- Odczyt „Skorppłonłca Nałka” ze zgłoszenia do wersji 1.9.2 jest teraz dopasowywany do nazwy „Skorpionica Najka” z listy Dark Souls II.
- Dodano ustawienie „Podobieństwo nazwy bossa” w sekcji „Wykrywanie” (`bosses.name_match_ratio` w konfiguracji). Określa, jak bardzo odczyt OCR może różnić się od znanej nazwy, aby nadal ją otrzymał. Domyślny próg obniżono z 0,80 do 0,60, dzięki czemu poprawianych jest więcej błędów odczytu. Wartość 0,50 też zadziała, ale wtedy boss spoza listy łatwiej dostaje cudzą nazwę, na przykład „Demon z Azylu” przy wybranym Dark Souls II zostałby dopasowany do „Demon kuźni”.

## 1.9.2

- Dodano odczyt nazw bossów z obrazu w odcieniach szarości obok dotychczasowych wariantów czarno-białych. Zachowuje on cienkie kreski i wygładzanie liter, które mogą zanikać podczas progowania obrazu.
- Zmiana odpowiada na zgłoszenie z Dark Souls II: nazwa „Skorpionica Naika” została odczytana jako „Skorppłonłca Nałka”. Skuteczność dla tego konkretnego obrazu wymaga jeszcze sprawdzenia w grze, ponieważ nie mamy źródłowego zrzutu ekranu.
- Dodano test zachowania odcieni liter oraz test potwierdzający, że ręczna korekta tej nazwy jest zapamiętywana również po ponownym wczytaniu danych.
