# Historia zmian

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
