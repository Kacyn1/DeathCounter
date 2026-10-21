"""Tłumaczenie angielskie: polski tekst z kodu → tekst angielski (i18n.tr). Pola {nazwa} muszą się zgadzać."""

EN = {
    # app.py
    "Death Counter by MK – błąd": "Death Counter by MK – error",
    "Wystąpił nieoczekiwany błąd:\n{exc}": "An unexpected error occurred:\n{exc}",
    "Death Counter by MK – wybór gry": "Death Counter by MK – choose game",
    "Program zapisuje teraz licznik śmierci, bossów i kalibrację osobno dla każdej gry.\n"
    "Do której gry należą dotychczasowe dane?":
        "The program now keeps the death counter, bosses and calibration separately for each game.\n"
        "Which game does the existing data belong to?",
    "Program jest już uruchomiony.": "The program is already running.",
    "Nie można przygotować pliku wyniku.\n\n{exc}": "Cannot prepare the score file.\n\n{exc}",

    # attempts.py
    "Śmierć": "Death",
    "Śmierć (ręcznie)": "Death (manual)",
    "Zwycięstwo": "Victory",
    "Przerwano (opuszczono arenę)": "Abandoned (left the arena)",
    "Przerwano (zatrzymano wykrywanie)": "Interrupted (detection stopped)",
    "Cofnięto (−1)": "Undone (−1)",
    "W toku": "In progress",
    "Nie można odczytać {name} ({exc}); historia prób zacznie się od nowa.":
        "Cannot read {name} ({exc}); the attempt history will start over.",
    "dziś {moment:%H:%M}": "today {moment:%H:%M}",
    "Brak zapisanych prób – historia prób zbiera się od wersji 1.8.0.":
        "No saved attempts – attempt history has been recorded since version 1.8.0.",
    "Próby: {count_attempts}": "Attempts: {count_attempts}",
    "średnio {time}": "average {time}",
    "najdłuższa {time}": "longest {time}",
    "pokonany w {won}. próbie": "defeated on attempt {won}",

    # audit.py
    "oczekiwano obiektu JSON": "expected a JSON object",
    "Rejestr zmian {name} jest uszkodzony – wynik tej gry będzie oznaczony jako niepewny.":
        "The change log {name} is damaged – this game's result will be marked as unverified.",
    "Rejestr zmian {name} został zmieniony poza programem – wynik tej gry będzie oznaczony jako niepewny.":
        "The change log {name} was modified outside the program – this game's result will be marked as unverified.",
    "Nie można zapisać rejestru zmian: {exc}": "Cannot save the change log: {exc}",

    # boss_names.py
    "Nie można odczytać {name} ({exc}); lista znanych bossów zacznie się od nowa.":
        "Cannot read {name} ({exc}); the list of known bosses will start over.",

    # boss_panel.py
    "W TRAKCIE": "IN PROGRESS",
    "PRZERWANO": "ABANDONED",
    "POKONANO": "DEFEATED",
    "Walka z bossem": "Boss fight",
    "Śledź walkę z bossem": "Track boss fights",
    "Walka zaczyna się sama, gdy na ekranie pojawi się pasek zdrowia bossa. Śmierć pauzuje timer,\n"
    "a komunikat zwycięstwa zatrzymuje go na stałe. Ty tylko zatwierdzasz wynik.":
        "The fight starts by itself when the boss health bar appears on screen. A death pauses the timer,\n"
        "and the victory message stops it for good. You only confirm the result.",
    "Odczytuj nazwę bossa z ekranu": "Read the boss name from the screen",
    "Po pojawieniu się paska program czyta nazwę nad nim (OCR Windows, po polsku albo po angielsku).\n"
    "Poprawiona ręcznie nazwa zostaje zapamiętana – następnym razem boss zostanie rozpoznany od razu.\n"
    "Gdy w trakcie walki pojawi się inny boss, walka przechodzi na niego.":
        "When the bar appears, the program reads the name above it (Windows OCR, Polish or English).\n"
        "A name you correct by hand is remembered – next time the boss is recognized right away.\n"
        "If a different boss appears during the fight, the fight switches to it.",
    "Status:": "Status:",
    "nazwę możesz wpisać w dowolnym momencie": "you can type the name at any time",
    "Boss:": "Boss:",
    "Zapisz wynik": "Save result",
    "Zapisuje ostateczny wynik do bosses.json ze statusem POKONANO i czyści panel.":
        "Saves the final result to bosses.json with the DEFEATED status and clears the panel.",
    "Kontynuuj walkę": "Continue fight",
    "To nie było zwycięstwo – walka z tym bossem trwa dalej.": "That was not a victory – the fight with this boss goes on.",
    "Odrzuć": "Discard",
    "Pomyłka (np. fałszywy start) – wpis zostanie usunięty bez zapisu wyniku.":
        "A mistake (e.g. a false start) – the entry will be removed without saving a result.",
    "Ostatnie walki:": "Recent fights:",
    "Pokonany": "Defeated",
    "To była wygrana, której program nie wykrył – zapisz wynik jako POKONANO.":
        "This was a win the program did not detect – save the result as DEFEATED.",
    "Usuń": "Remove",
    "Pomyłka (np. przebiegnięcie obok bossa) – usuwa bossa razem z wynikiem.":
        "A mistake (e.g. running past a boss) – removes the boss together with its result.",
    "Kalibracja walki…": "Fight calibration…",
    "Wzorce paska zdrowia bossa i komunikatu zwycięstwa.": "Templates for the boss health bar and the victory message.",
    "Wyniki…": "Results…",
    "Tabela wszystkich bossów tej gry: śmierci, czas i status.": "A table of all bosses in this game: deaths, time and status.",
    "brak aktywnej walki": "no active fight",
    "śledzenie wyłączone": "tracking off",
    "śmierci: {deaths}   czas: {seconds}": "deaths: {deaths}   time: {seconds}",
    "Nazwa bossa jest niepewna – sprawdź ją (możesz poprawić) i kliknij „Zapisz wynik”.":
        "The boss name is uncertain – check it (you can correct it) and click “Save result”.",
    "{name} · <b style='color:{color}'>{status}</b> · śmierci: {deaths} · {seconds} · "
    "<span style='color:#7d828a'>{time}</span>":
        "{name} · <b style='color:{color}'>{status}</b> · deaths: {deaths} · {seconds} · "
        "<span style='color:#7d828a'>{time}</span>",
    "Usuń walkę": "Remove fight",
    "Usunąć „{name}” razem z wynikiem (śmierci: {deaths}, czas: {seconds})?":
        "Remove “{name}” together with its result (deaths: {deaths}, time: {seconds})?",
    "Odrzuć walkę": "Discard fight",
    "Usunąć „{current}” bez zapisu wyniku?": "Remove “{current}” without saving a result?",
    "Nie zapisano danych bossa: {exc} Kolejna zmiana ponowi zapis.":
        "Boss data was not saved: {exc} The next change will retry saving.",

    # bosses.py
    "Oczekiwanie": "Waiting",
    "Walka": "Fight",
    "Boss pokonany": "Boss defeated",
    "Nie można odczytać pliku {name}: {exc}": "Cannot read the file {name}: {exc}",
    "Plik {name} jest uszkodzony ({exc}) i nie można go odłożyć: {move_exc}":
        "The file {name} is damaged ({exc}) and cannot be moved aside: {move_exc}",
    "Plik {name} był uszkodzony ({exc}). Jego kopię zapisano jako {name2}, a lista bossów zaczyna się od nowa.":
        "The file {name} was damaged ({exc}). A copy was saved as {name2}, and the boss list starts over.",
    "Śmierć i komunikat zwycięstwa prawie jednocześnie – zatwierdź wynik.":
        "Death and victory message almost at the same time – confirm the result.",
    "Komunikat zwycięstwa po śmierci – zatwierdź wynik albo kontynuuj walkę.":
        "Victory message after a death – confirm the result or continue the fight.",
    "Utracono obraz w trakcie walki – kontynuuj walkę albo zatwierdź wynik.":
        "The image was lost during the fight – continue the fight or confirm the result.",
    "{name} — deaths: {deaths}": "{name} — deaths: {deaths}",
    "Sesja: {deaths} · {time}": "Session: {deaths} · {time}",
    "Czas: {seconds}": "Time: {seconds}",
    "niepoprawny JSON": "invalid JSON",
    "wpis „{name}” nie jest obiektem": "entry “{name}” is not an object",
    "„{name}”: pole \"deaths\" nie jest liczbą nieujemną": "“{name}”: the \"deaths\" field is not a non-negative number",
    "„{name}”: pole \"total_time_seconds\" nie jest liczbą nieujemną":
        "“{name}”: the \"total_time_seconds\" field is not a non-negative number",
    "„{name}”: nieznany status {status!r}": "“{name}”: unknown status {status!r}",

    # calibration.py
    "Brak obrazu – przechwyć ekran lub wczytaj zrzut.": "No image – capture the screen or load a screenshot.",
    "napis śmierci": "death message",
    "gdy widać ekran śmierci (np. „NIE ŻYJESZ”)": "when the death screen is visible (e.g. “YOU DIED”)",
    "Zaznacz myszą prostokąt obejmujący <b>sam napis</b>, z niewielkim marginesem.":
        "Drag a rectangle around <b>just the text</b>, with a small margin.",
    "Na ekranie śmierci wynik powinien przekroczyć próg, a na zwykłym zrzucie z gry być wyraźnie niższy.":
        "On the death screen the score should exceed the threshold, and on a regular game screenshot be clearly lower.",
    "pasek zdrowia bossa": "boss health bar",
    "w trakcie walki, gdy widać pasek zdrowia bossa": "during a fight, when the boss health bar is visible",
    "Zaznacz <b>lewy koniec paska</b>: ozdobną ramkę i początek paska. Nie zaznaczaj nazwy bossa "
    "(każdy boss ma inną) ani całego paska – jego wypełnienie maleje, gdy boss traci zdrowie.":
        "Select <b>the left end of the bar</b>: the decorative frame and the start of the bar. Do not select the "
        "boss name (every boss has a different one) or the whole bar – its fill shrinks as the boss loses health.",
    "Na obrazie z walki wynik powinien przekroczyć próg, a na zrzucie bez bossa być wyraźnie niższy.":
        "On a fight image the score should exceed the threshold, and on a screenshot without a boss be clearly lower.",
    "komunikat zwycięstwa": "victory message",
    "gdy po pokonaniu bossa widać komunikat zwycięstwa": "when the victory message is visible after defeating a boss",
    "Zaznacz myszą prostokąt obejmujący <b>sam napis</b> komunikatu, z niewielkim marginesem.":
        "Drag a rectangle around <b>just the text</b> of the message, with a small margin.",
    "Na obrazie z komunikatem wynik powinien przekroczyć próg, a na zwykłym zrzucie z gry być wyraźnie niższy.":
        "On an image with the message the score should exceed the threshold, and on a regular game screenshot be "
        "clearly lower.",
    "naciśnij <b>{hotkey_text}</b> w grze {moment}": "press <b>{hotkey_text}</b> in the game {moment}",
    "użyj przechwytywania z opóźnieniem": "use delayed capture",
    "<ol style='margin:0'><li>Pobierz obraz, na którym widać {subject}: {hotkey}, przechwyć ekran z opóźnieniem "
    "albo wczytaj zrzut ekranu z gry (np. F12 w Steam).</li><li>{what_to_select}</li><li>Kliknij „Sprawdź "
    "wzorzec”. {check_hint}</li><li>Kliknij „Zapisz wzorzec”.</li></ol>":
        "<ol style='margin:0'><li>Get an image showing the {subject}: {hotkey}, capture the screen with a delay or "
        "load a game screenshot (e.g. F12 in Steam).</li><li>{what_to_select}</li><li>Click “Check template”. "
        "{check_hint}</li><li>Click “Save template”.</li></ol>",
    "Przechwyć ekran": "Capture screen",
    "Wczytaj zrzut z pliku…": "Load screenshot from file…",
    "Zrzut ze skrótu": "Hotkey screenshot",
    "Wstawia ostatni zrzut zrobiony skrótem {value}.": "Inserts the last screenshot taken with the {value} hotkey.",
    "zrzutu": "screenshot",
    "Pokaż zapisany wzorzec": "Show saved template",
    "Wraca do obrazu, z którego wycięto zapisany wzorzec, z zaznaczonym obszarem.":
        "Goes back to the image the saved template was cut from, with the area selected.",
    "Opóźnienie:": "Delay:",
    "Ten wzorzec zapisano we wcześniejszej wersji programu, bez pełnego zrzutu – widać tylko zaznaczony fragment. "
    "Po ponownym zapisaniu wzorca kalibracja będzie pokazywać cały obraz.":
        "This template was saved by an earlier version of the program, without the full screenshot – only the "
        "selected part is visible. After saving the template again, calibration will show the whole image.",
    "Sprawdź wzorzec": "Check template",
    "Zapisz wzorzec": "Save template",
    "Przechwytywanie za {remaining} s…": "Capturing in {remaining} s…",
    "Przechwytywanie…": "Capturing…",
    "Kalibracja": "Calibration",
    "Nie udało się pobrać obrazu.": "Could not get an image.",
    "Wybierz zrzut ekranu": "Choose a screenshot",
    "Obrazy (*.png *.jpg *.jpeg *.bmp);;Wszystkie pliki (*)": "Images (*.png *.jpg *.jpeg *.bmp);;All files (*)",
    "<span style='color:#e0a050'>wzorzec: brak</span>": "<span style='color:#e0a050'>template: none</span>",
    "<span style='color:#5fd38d'>wzorzec: zapisany (z obrazu {w}×{h})</span>":
        "<span style='color:#5fd38d'>template: saved (from a {w}×{h} image)</span>",
    "Zaznaczenie: brak": "Selection: none",
    " – zapisany wzorzec": " – saved template",
    "Zaznaczenie: {w}×{h} px w punkcie ({x}, {y}){saved}": "Selection: {w}×{h} px at ({x}, {y}){saved}",
    "Zaznacz {subject} na obrazie.": "Select the {subject} in the image.",
    "<b style='color:#5fd38d'>WYKRYTO</b>": "<b style='color:#5fd38d'>DETECTED</b>",
    "<b style='color:#e0a050'>NIE WYKRYTO</b>": "<b style='color:#e0a050'>NOT DETECTED</b>",
    "zaznaczenia": "the selection",
    "zapisanego wzorca": "the saved template",
    "Dopasowanie {source} do tego obrazu: <b>{score:.2f}</b> (próg {threshold:.2f}) → {verdict}":
        "Match of {source} to this image: <b>{score:.2f}</b> (threshold {threshold:.2f}) → {verdict}",
    "Błąd zapisu wzorca": "Template save error",
    "<span style='color:#5fd38d'>Wzorzec zapisany i używany przez wykrywanie.</span>":
        "<span style='color:#5fd38d'>Template saved and used by detection.</span>",
    "Kalibracja wzorców": "Template calibration",
    "Napis śmierci": "Death message",
    "Pasek bossa": "Boss bar",
    "Komunikat zwycięstwa": "Victory message",
    "Pasek bossa rozpoczyna walkę i wznawia timer, a komunikat zwycięstwa kończy ją na stałe. Skalibruj oba, "
    "aby „Śledź walkę z bossem” działało samo.":
        "The boss bar starts a fight and resumes the timer, and the victory message ends it for good. Calibrate "
        "both so that “Track boss fights” works on its own.",
    "Zamknij": "Close",

    # capture.py
    " (główny)": " (primary)",
    "Monitor {value}: {width}×{height}{primary}": "Monitor {value}: {width}×{height}{primary}",
    "Nie można załadować biblioteki DXCam: {exc}": "Cannot load the DXCam library: {exc}",
    "Nie można uruchomić przechwytywania obrazu: {exc}": "Cannot start screen capture: {exc}",
    "DXCam nie zwrócił źródła obrazu dla wybranego monitora.": "DXCam returned no image source for the selected monitor.",
    "Przechwytywanie nie jest uruchomione.": "Capture is not running.",
    "Brak obrazu: nie udało się pobrać klatki z wybranego monitora.":
        "No image: could not get a frame from the selected monitor.",

    # config.py
    "Podaj nazwę gry.": "Enter a game name.",
    "Nazwa gry może mieć najwyżej {GAME_NAME_MAX} znaków.": "The game name can be at most {GAME_NAME_MAX} characters long.",
    "Gra „{name}” jest już na liście.": "The game “{name}” is already on the list.",
    "Nie można odczytać {name} ({exc}). Użyto ustawień domyślnych.": "Cannot read {name} ({exc}). Default settings were used.",
    "Nie można odczytać {name} ({exc}). Wykonaj kalibrację ponownie.": "Cannot read {name} ({exc}). Calibrate again.",
    "Nie można przenieść danych do folderu gry {game_dir}: {exc}": "Cannot move the data to the game folder {game_dir}: {exc}",
    "Brak folderu z prawem zapisu na dane programu: {exc}": "No writable folder for the program data: {exc}",

    # discord_presence.py
    "Discord zamknął połączenie.": "Discord closed the connection.",
    "Discord nie jest uruchomiony.": "Discord is not running.",
    "Śmierci: {deaths}": "Deaths: {deaths}",
    "Nie udało się połączyć z Discordem: {exc}": "Could not connect to Discord: {exc}",
    "Discord odrzucił połączenie: {value}": "Discord rejected the connection: {value}",
    "Brak połączenia z Discordem.": "Not connected to Discord.",
    "Połączenie z Discordem zostało przerwane: {exc}": "The connection to Discord was interrupted: {exc}",
    "Discord odrzucił status: {get}": "Discord rejected the status: {get}",
    "połączono z Discordem": "connected to Discord",
    "status ustawiony": "status set",
    "status wyczyszczony": "status cleared",

    # game_data.py
    "napisu śmierci": "death message",
    "paska bossa": "boss bar",
    "komunikatu zwycięstwa": "victory message",
    "Nie można utworzyć folderu gry {game_dir}: {exc}": "Cannot create the game folder {game_dir}: {exc}",
    "Nie można wczytać wzorca {item}: {exc} Wykonaj kalibrację ponownie.":
        "Cannot load the {item} template: {exc} Calibrate again.",

    # hotkey_dialog.py
    "Zrzut do kalibracji:": "Calibration screenshot:",
    "Dodaj +1:": "Add +1:",
    "Cofnij −1:": "Undo −1:",
    "Nakładka włącz/wyłącz:": "Overlay on/off:",
    "Skróty klawiszowe": "Hotkeys",
    "Skróty działają globalnie – także w grze na pełnym ekranie. Kliknij pole i naciśnij nową kombinację klawiszy; "
    "przycisk ✕ w polu wyłącza skrót.":
        "Hotkeys work globally – also in a fullscreen game. Click a field and press a new key combination; the ✕ "
        "button in the field turns the hotkey off.",
    "Przywróć domyślne": "Restore defaults",
    "{display} jest już przypisany do „{item}”.": "{display} is already assigned to “{item}”.",

    # hotkeys.py
    "Skrót jest pusty.": "The hotkey is empty.",
    "Nieznany modyfikator „{mod}” w skrócie {text}.": "Unknown modifier “{mod}” in the hotkey {text}.",
    "Klawisz „{value}” nie może być skrótem globalnym.": "The key “{value}” cannot be a global hotkey.",
    "Skrót {text} blokowałby pisanie – dodaj Ctrl, Alt albo Win.": "The hotkey {text} would block typing – add Ctrl, Alt or Win.",

    # legal.py
    "Ten program jest wolnym oprogramowaniem: możesz go rozpowszechniać i/lub modyfikować na warunkach "
    "Powszechnej Licencji Publicznej GNU (GNU GPL) w wersji 3, opublikowanej przez Free Software Foundation. "
    "Program jest rozpowszechniany bez jakiejkolwiek gwarancji – szczegóły w treści licencji.":
        "This program is free software: you can redistribute it and/or modify it under the terms of the GNU "
        "General Public License (GNU GPL) version 3, as published by the Free Software Foundation. The program "
        "is distributed without any warranty – see the license text for details.",
    "Brak pliku {name}. Pełny tekst jest dostępny na {REPOSITORY}.": "The file {name} is missing. The full text is available at {REPOSITORY}.",
    "O programie": "About",
    "<h2 style='margin:0'>Death Counter by MK</h2><p>Wersja {version}</p><p>{COPYRIGHT}</p><p>{LICENSE_NOTICE}</p>"
    "<p>Kod źródłowy: <a href='{REPOSITORY}'>{REPOSITORY}</a></p><p style='color:#9aa0a6'>Program korzysta z "
    "bibliotek Qt for Python (LGPL v3), OpenCV (Apache 2.0), NumPy (BSD), DXcam, comtypes i PyWinRT (MIT) oraz "
    "Pythona (PSF).</p>":
        "<h2 style='margin:0'>Death Counter by MK</h2><p>Version {version}</p><p>{COPYRIGHT}</p><p>{LICENSE_NOTICE}</p>"
        "<p>Source code: <a href='{REPOSITORY}'>{REPOSITORY}</a></p><p style='color:#9aa0a6'>The program uses Qt "
        "for Python (LGPL v3), OpenCV (Apache 2.0), NumPy (BSD), DXcam, comtypes and PyWinRT (MIT) and Python "
        "(PSF).</p>",
    "Licencja (GNU GPL v3)…": "License (GNU GPL v3)…",
    "Licencje bibliotek…": "Library licenses…",
    "Licencje bibliotek osób trzecich": "Third-party library licenses",

    # main_window.py
    "Okno + RTSS": "Window + RTSS",
    "Okno na wierzchu": "Window on top",
    "Tylko RTSS (pełny ekran)": "RTSS only (fullscreen)",
    "Każda gra ma własny licznik śmierci, bossów i kalibrację.\n„+ Dodaj grę…” tworzy nowy licznik dla gry spoza "
    "listy, a „Znajdź zainstalowane gry ze Steam…”\ndodaje liczniki dla gier souls-like.":
        "Each game has its own death counter, bosses and calibration.\n“+ Add game…” creates a new counter for a "
        "game that is not on the list, and “Find installed Steam games…”\nadds counters for souls-like games.",
    "Usuń licznik": "Delete counter",
    "Resetuj licznik": "Reset counter",
    "Gra znika z listy razem z licznikiem, bossami i kalibracją. Pliki trafiają do Kosza.":
        "The game disappears from the list together with its counter, bosses and calibration. Files go to the "
        "Recycle Bin.",
    "Gier FromSoftware nie można usunąć z listy. Reset zeruje licznik śmierci i bossów,\na kalibracja zostaje. "
    "Pliki trafiają do Kosza.":
        "FromSoftware games cannot be removed from the list. A reset clears the death counter and bosses,\nand the "
        "calibration stays. Files go to the Recycle Bin.",
    "Czy na pewno chcesz zresetować licznik {name}?": "Are you sure you want to reset the {name} counter?",
    "Zresetowano licznik {name} (pliki są w Koszu).": "Reset the {name} counter (the files are in the Recycle Bin).",
    "Znajdź zainstalowane gry ze Steam…": "Find installed Steam games…",
    "Gry ze Steama": "Steam games",
    "Na tym komputerze jest Steam. Sprawdzić zainstalowane gry i dodać liczniki dla gier souls-like?\n\n"
    "Później zrobisz to pozycją „Znajdź zainstalowane gry ze Steam…” na liście gier.":
        "Steam is installed on this computer. Check the installed games and add counters for souls-like games?\n\n"
        "You can do it later with “Find installed Steam games…” on the game list.",
    "Dodano gry ze Steama: {names}. Wybierz grę z listy i wykonaj kalibrację.":
        "Added Steam games: {names}. Choose a game from the list and calibrate it.",
    "Gra:": "Game:",
    "ŚMIERCI": "DEATHS",
    "Stan": "Status",
    "Wykrywanie:": "Detection:",
    "Obraz:": "Image:",
    "Dopasowanie:": "Match:",
    "Wzorce:": "Templates:",
    "Start": "Start",
    "Dodaj +1": "Add +1",
    "Cofnij -1": "Undo -1",
    "Reset": "Reset",
    "Kalibracja…": "Calibration…",
    "Certyfikat PDF…": "PDF certificate…",
    "Certyfikat wybranej gry: śmierci, pokonani bossowie i ich czasy, z kodem weryfikacyjnym.":
        "A certificate for the selected game: deaths, defeated bosses and their times, with a verification code.",
    "Sprawdź certyfikat…": "Verify certificate…",
    "Sprawdza, czy plik PDF jest prawdziwym, niezmienionym certyfikatem.":
        "Checks whether a PDF file is a genuine, unmodified certificate.",
    "Skróty…": "Hotkeys…",
    "Zmiana skrótów klawiszowych działających w grze.": "Change the hotkeys that work in the game.",
    "Nakładka": "Overlay",
    "Okno na wierzchu działa w trybie okienkowym, a w pełnym ekranie tylko wtedy, gdy Windows\nstosuje "
    "optymalizacje pełnego ekranu. RTSS (RivaTuner Statistics Server) wyświetla licznik\ntakże w ekskluzywnym "
    "pełnym ekranie – musi być uruchomiony, a jego OSD włączone.\nPozycję i wielkość tekstu RTSS ustawia się "
    "w samym RTSS.":
        "The window on top works in windowed mode, and in fullscreen only when Windows\napplies fullscreen "
        "optimizations. RTSS (RivaTuner Statistics Server) shows the counter\nalso in exclusive fullscreen – it "
        "must be running with its OSD turned on.\nThe position and size of the RTSS text are set in RTSS itself.",
    "Niewidoczna dla nagrywania/OBS": "Hidden from recording/OBS",
    "Nakładka będzie widoczna tylko na monitorze, a nie na zrzutach i w programach do nagrywania.":
        "The overlay will only be visible on the monitor, not in screenshots or recording software.",
    "Tryb:": "Mode:",
    "Uruchamiaj RTSS razem z licznikiem": "Start RTSS together with the counter",
    "Zainstaluj RTSS…": "Install RTSS…",
    "Pozycja X:": "Position X:",
    "Pozycja Y:": "Position Y:",
    "Wielkość tekstu:": "Text size:",
    "Status na Discordzie": "Discord status",
    "Pokazuje w Twoim statusie na Discordzie grę i liczbę śmierci.": "Shows the game and death count in your Discord status.",
    "Discord:": "Discord:",
    "Wykrywanie": "Detection",
    "Minimalne dopasowanie obrazu do wzorca napisu śmierci, przy którym napis uznajemy za widoczny.\nTen sam "
    "próg dotyczy komunikatu zwycięstwa – oba to duże napisy na środku ekranu.":
        "The minimum match between the image and the death message template at which the message counts as "
        "visible.\nThe same threshold applies to the victory message – both are large texts in the middle of the screen.",
    "Minimalne dopasowanie obrazu do wzorca paska zdrowia bossa, przy którym walka się zaczyna.":
        "The minimum match between the image and the boss health bar template at which a fight starts.",
    "Minimalne podobieństwo nazwy odczytanej z ekranu do znanej nazwy bossa wybranej gry.\nOdczyt dostaje "
    "najbardziej podobną nazwę z listy, jeśli podobieństwo jest co najmniej takie.\nNiżej – więcej poprawionych "
    "błędów OCR, ale boss spoza listy łatwiej dostanie cudzą nazwę.\n1,00 – tylko nazwy odczytane bez błędu.":
        "The minimum similarity between the name read from the screen and a known boss name of the selected game.\n"
        "The reading gets the most similar name from the list if the similarity is at least this high.\nLower – "
        "more OCR errors corrected, but a boss not on the list more easily gets someone else's name.\n1.00 – only "
        "names read without errors.",
    " próbek": " samples",
    "Tyle kolejnych próbek (co ok. 0,1 s) musi zawierać napis, by zliczyć śmierć.":
        "This many consecutive samples (about every 0.1 s) must contain the message to count a death.",
    "Tyle sekund bez napisu, zanim detektor będzie gotowy na kolejną śmierć.":
        "This many seconds without the message before the detector is ready for the next death.",
    "Włączaj wykrywanie przy starcie": "Start detection on launch",
    "Monitor:": "Monitor:",
    "Próg śmierci i zwycięstwa:": "Death and victory threshold:",
    "Próg paska bossa:": "Boss bar threshold:",
    "Podobieństwo nazwy bossa:": "Boss name similarity:",
    "Potwierdzenie:": "Confirmation:",
    "Ponowne uzbrojenie:": "Re-arm after:",
    "Główny monitor": "Primary monitor",
    "Nie zapisano wyniku: {exc} Kolejna zmiana ponowi zapis.": "The score was not saved: {exc} The next change will retry saving.",
    "Błąd zapisu": "Save error",
    "Nie zapisano rejestru zmian: {exc}": "The change log was not saved: {exc}",
    "Walka przerwana (opuszczono arenę)": "Fight abandoned (left the arena)",
    "Automatycznie zapisany": "Saved automatically",
    "{what}: {name} – śmierci: {deaths}, czas: {seconds}": "{what}: {name} – deaths: {deaths}, time: {seconds}",
    "Popraw nazwy bossów": "Fix boss names",
    "Wszystkie nazwy bossów zgadzają się z listą nazw tej gry.": "All boss names match this game's name list.",
    "Te nazwy zostaną zamienione na nazwy z listy gry:\n\n{lines}\n\nLiczba śmierci, czas i historia prób "
    "przejdą pod nowe nazwy. Poprawić?":
        "These names will be replaced with names from the game's list:\n\n{lines}\n\nDeaths, time and attempt "
        "history will move to the new names. Fix them?",
    "Nie zapisano poprawionych nazw bossów: {fix_error}": "The fixed boss names were not saved: {fix_error}",
    "Poprawiono nazwy bossów: {count__fixed_names}.": "Boss names fixed: {count__fixed_names}.",
    "Poprawione nazwy bossów": "Fixed boss names",
    "Zapisane nazwy bossów porównano z listą nazw tej gry i poprawiono:\n\n{lines}\n\nLiczba śmierci, czas "
    "i historia prób przeszły pod nowe nazwy. Jeśli któraś zmiana jest zła, popraw tę nazwę ręcznie.":
        "Saved boss names were compared with this game's name list and fixed:\n\n{lines}\n\nDeaths, time and "
        "attempt history moved to the new names. If a change is wrong, correct that name by hand.",
    "+ Dodaj grę…": "+ Add game…",
    "Dodaj grę": "Add game",
    "Nazwa gry (np. Lies of P):\nGra dostanie własny licznik śmierci, bossów i kalibrację.":
        "Game name (e.g. Lies of P):\nThe game gets its own death counter, bosses and calibration.",
    "Zmiana gry": "Change game",
    "Nie można wczytać danych gry.\n\n{exc}": "Cannot load the game data.\n\n{exc}",
    "Wybrano grę: {game_name}.": "Game selected: {game_name}.",
    "Czy na pewno chcesz usunąć licznik {name}?": "Are you sure you want to delete the {name} counter?",
    "Gra zniknie z listy, a jej licznik śmierci, bossowie i kalibracja trafią do Kosza.":
        "The game will disappear from the list, and its death counter, bosses and calibration will go to the Recycle Bin.",
    "Licznik śmierci ({deaths}) i lista bossów trafią do Kosza. Gra zostaje na liście, a jej kalibracja się nie zmienia.":
        "The death counter ({deaths}) and the boss list will go to the Recycle Bin. The game stays on the list, "
        "and its calibration does not change.",
    "Tak": "Yes",
    "Nie": "No",
    "Nie udało się usunąć licznika {name}.\n\n{exc}": "Could not delete the {name} counter.\n\n{exc}",
    "Usunięto licznik {name} (pliki są w Koszu).": "Deleted the {name} counter (the files are in the Recycle Bin).",
    "Dane gry: {game_dir}": "Game data: {game_dir}",
    "Certyfikat PDF": "PDF certificate",
    "Nick gracza na certyfikacie (możesz zostawić puste):": "Player name on the certificate (you can leave it empty):",
    "DeathCounter_certyfikat_{game}_{now:%Y-%m-%d}.pdf": "DeathCounter_certificate_{game}_{now:%Y-%m-%d}.pdf",
    "Zapisz certyfikat PDF": "Save PDF certificate",
    "Dokument PDF (*.pdf)": "PDF document (*.pdf)",
    "Nie udało się zapisać certyfikatu.\n\n{exc}": "Could not save the certificate.\n\n{exc}",
    " – bez podpisu: ta wersja programu nie ma klucza": " – unsigned: this version of the program has no key",
    "Zapisano certyfikat{signed}: {path}": "Certificate saved{signed}: {path}",
    "Sprawdź certyfikat": "Verify certificate",
    "Certyfikat jest prawdziwy": "The certificate is genuine",
    "Certyfikat został zmieniony albo podrobiony": "The certificate was modified or forged",
    "Certyfikat bez podpisu": "Unsigned certificate",
    "Nie można sprawdzić podpisu": "The signature cannot be checked",
    "To nie jest certyfikat Death Counter by MK": "This is not a Death Counter by MK certificate",
    "Dane i kod weryfikacyjny zgadzają się z podpisem. Sprawdź, czy poniższe dane są takie same jak na "
    "certyfikacie – tylko te zostały podpisane.":
        "The data and the verification code match the signature. Check that the data below is the same as on "
        "the certificate – only this data was signed.",
    "Dane zapisane w pliku nie pasują do kodu weryfikacyjnego.": "The data stored in the file does not match the verification code.",
    "Certyfikat wystawiła wersja programu bez klucza podpisu (uruchomiona ze źródeł).":
        "The certificate was issued by a version of the program without a signing key (run from source).",
    "Ta wersja programu nie ma klucza podpisu. Użyj oficjalnego DeathCounter.exe.":
        "This version of the program has no signing key. Use the official DeathCounter.exe.",
    "Plik nie zawiera danych certyfikatu (to inny PDF albo zapisany ponownie w innym programie).":
        "The file contains no certificate data (it is another PDF or was saved again in another program).",
    "   • {name}: {deaths} śmierci, {seconds}": "   • {name}: {deaths} deaths, {seconds}",
    "   brak": "   none",
    " (w trakcie)": " (in progress)",
    "brak danych (certyfikat sprzed rejestru zmian)": "no data (certificate older than the change log)",
    "bez ręcznych zmian": "no manual changes",
    "\n\nGra: {game}\nGracz: {value}\nŚmierci: {deaths}\nWystawiono: {issued:%d.%m.%Y, %H:%M}\nKod: {value2}\n"
    "Korekty: {changes}\nBossowie:\n{bosses}":
        "\n\nGame: {game}\nPlayer: {value}\nDeaths: {deaths}\nIssued: {issued:%Y-%m-%d, %H:%M}\nCode: {value2}\n"
        "Adjustments: {changes}\nBosses:\n{bosses}",
    "Brak wzorca: {join}. Kliknij „Kalibracja walki…”, aby walka startowała sama.":
        "Missing template: {join}. Click “Fight calibration…” so that fights start by themselves.",
    "Wykrywanie jest wyłączone – kliknij Start, aby walka była rozpoznawana.":
        "Detection is off – click Start so that fights are recognized.",
    "Walka zacznie się sama, gdy na ekranie pojawi się pasek zdrowia bossa.":
        "The fight will start by itself when the boss health bar appears on screen.",
    "łączenie z Discordem…": "connecting to Discord…",
    "wyłączony": "off",
    "brak ID aplikacji Discord (patrz README)": "no Discord application ID (see README)",
    "Reset licznika": "Reset counter",
    "Czy na pewno wyzerować licznik? Obecna wartość ({deaths}) zostanie utracona.":
        "Are you sure you want to reset the counter? The current value ({deaths}) will be lost.",
    "Najpierw wykonaj kalibrację (przycisk „Kalibracja…”).": "Calibrate first (the “Calibration…” button).",
    "Stop": "Stop",
    "Uruchamianie przechwytywania…": "Starting capture…",
    "Zatrzymywanie…": "Stopping…",
    "Wykrywanie zostało zatrzymane przed pobraniem obrazu.": "Detection was stopped before an image was captured.",
    "brak nowych klatek": "no new frames",
    "zamrożony": "frozen",
    "brak klatek": "no frames",
    "czeka na zniknięcie napisu": "waiting for the message to disappear",
    "{score:.2f} (próg {threshold:.2f}) – detektor {armed}": "{score:.2f} (threshold {threshold:.2f}) – detector {armed}",
    "zwycięstwo {victory_score:.2f}/{threshold:.2f}": "victory {victory_score:.2f}/{threshold:.2f}",
    "Brak wzorca – wykonaj kalibrację, aby włączyć wykrywanie.": "No template – calibrate to turn detection on.",
    "Wykrywanie wyłączone. Kliknij Start.": "Detection is off. Click Start.",
    "nieużywany": "not used",
    "nakładka wyłączona": "overlay off",
    "Ukryj nakładkę": "Hide overlay",
    "Pokaż nakładkę": "Show overlay",
    "Nakładka:": "Overlay:",
    "Widoczna": "Visible",
    "Częściowo": "Partly",
    "Niewidoczna": "Not visible",
    "Ukryta": "Hidden",
    "Kliknij „Pokaż nakładkę”, żeby widzieć licznik w grze.": "Click “Show overlay” to see the counter in the game.",
    "RTSS – licznik widać także w pełnym ekranie.": "RTSS – the counter is visible in fullscreen too.",
    "{problem} – uruchom RTSS albo zmień tryb nakładki.": "{problem} – start RTSS or change the overlay mode.",
    "Okno widoczne, ale {problem} – w pełnym ekranie licznika może nie być widać.":
        "Window visible, but {problem} – in fullscreen the counter may not be visible.",
    "Okno na wierzchu i RTSS.": "Window on top and RTSS.",
    "Okno na wierzchu.": "Window on top.",
    "Jeśli w grze go nie widać (pełny ekran), wybierz tryb z RTSS.":
        "If you cannot see it in the game (fullscreen), choose a mode with RTSS.",
    "licznik przekazany do RTSS": "counter sent to RTSS",
    "RTSS nie jest uruchomiony – licznik pojawi się, gdy go włączysz": "RTSS is not running – the counter will appear when you start it",
    "Brak obrazu z wybranego monitora.": "No image from the selected monitor.",
    "Wzorzec zapisany, ale bez zrzutu do podglądu: {exc}": "Template saved, but without a preview screenshot: {exc}",
    "śmierć": "death",
    "pasek bossa": "boss bar",
    "zwycięstwo": "victory",
    "{label}: {value}": "{label}: {value}",
    "brak": "none",
    "skrótu": "hotkey",
    "Zrzut ze skrótu {text} nieudany: {error}": "The {text} hotkey screenshot failed: {error}",
    "Zapamiętano zrzut ekranu ({text}). Otwórz „Kalibracja…”, aby zaznaczyć napis.":
        "Screenshot saved ({text}). Open “Calibration…” to select the message.",
    "Skróty zajęte przez inny program albo system: {join}.": "Hotkeys taken by another program or the system: {join}.",
    "Skrót w grze: {text}": "In-game hotkey: {text}",
    "Zapisano skróty klawiszowe.": "Hotkeys saved.",
    "Do wyświetlania licznika nad grą w pełnym ekranie potrzebny jest darmowy program RivaTuner Statistics Server "
    "(RTSS).\n\nZainstalować go teraz? Instalacja pobierze oficjalną paczkę Guru3D przez winget, a Windows "
    "poprosi o zgodę administratora.":
        "Showing the counter over a fullscreen game requires the free RivaTuner Statistics Server (RTSS).\n\n"
        "Install it now? The installation downloads the official Guru3D package through winget, and Windows "
        "will ask for administrator permission.",
    "RTSS możesz zainstalować później przyciskiem „Zainstaluj RTSS…”.": "You can install RTSS later with the “Install RTSS…” button.",
    "Co nowego": "What's new",
    "Aktualizuj": "Update",
    "Później": "Later",
    "Ukrywa pasek do następnego uruchomienia programu.": "Hides the bar until the program is started again.",
    "Zaktualizowano do wersji {version}.": "Updated to version {version}.",
    "Sprawdzanie…": "Checking…",
    "Masz najnowszą wersję ({version}).": "You have the latest version ({version}).",
    "Dostępna wersja {version}.": "Version {version} is available.",
    "Dostępna nowa wersja <b>{version}</b> (masz {version2}).": "A new version is available: <b>{version}</b> (you have {version2}).",
    "Program uruchomiony ze źródeł – zaktualizuj go poleceniem git pull.": "The program runs from source – update it with git pull.",
    "Pobiera nową wersję, podmienia program i uruchamia go ponownie.": "Downloads the new version, replaces the program and restarts it.",
    "Aktualizacja": "Update",
    "Trwa walka z bossem. Program zapisze jej czas i uruchomi się ponownie w nowej wersji. Kontynuować?":
        "A boss fight is in progress. The program will save its time and restart in the new version. Continue?",
    "Pobieranie wersji {version}…": "Downloading version {version}…",
    "Aktualizacja nieudana: {error}": "Update failed: {error}",
    "Uruchamianie wersji {version}…": "Starting version {version}…",
    "Język programu i nazw bossów. Zmiana uruchamia program ponownie.":
        "The language of the program and boss names. Changing it restarts the program.",
    "Język:": "Language:",
    "Sprawdzaj aktualizacje raz dziennie": "Check for updates once a day",
    "Program raz na dobę pyta GitHuba o najnowsze wydanie. Niczego nie instaluje bez Twojej zgody.":
        "Once a day the program asks GitHub for the latest release. It never installs anything without your consent.",
    "Sprawdź aktualizacje": "Check for updates",
    "Kończenie konfiguracji RTSS – program zamknie się za chwilę.": "Finishing RTSS setup – the program will close in a moment.",
    "Nie zapisano ustawień: {exc}": "Settings were not saved: {exc}",

    # ocr.py
    "brak modułu OCR Windows ({exc})": "the Windows OCR module is missing ({exc})",
    "Windows nie ma pakietu rozpoznawania tekstu (Ustawienia → Czas i język → Język i region → Polski albo "
    "English → Opcje językowe → Optyczne rozpoznawanie znaków)":
        "Windows has no text recognition package (Settings → Time & language → Language & region → English or "
        "Polski → Language options → Optical character recognition)",

    # overlay.py
    "Death Counter by MK – nakładka": "Death Counter by MK – overlay",

    # recent_fights.py
    "Nie można odczytać {name} ({exc}); lista ostatnich walk zacznie się od nowa.":
        "Cannot read {name} ({exc}); the list of recent fights will start over.",

    # report.py
    "Licznik ogólny": "Overall counter",
    "rejestr zmian został naruszony – wynik niewiarygodny": "the change log was tampered with – the result is unreliable",
    "ręczne korekty śmierci: +{manual_added} / −{manual_removed}": "manual death corrections: +{manual_added} / −{manual_removed}",
    "licznik zmieniony poza programem: {deaths:+d}": "counter changed outside the program: {deaths:+d}",
    "lista bossów zmieniona poza programem": "boss list changed outside the program",
    "{untracked_deaths} śmierci bez historii zmian": "{untracked_deaths} deaths without change history",
    "ręczne korekty śmierci przy bossach: {manual}": "manual boss death corrections: {manual}",
    "bossowie zmienieni poza programem: {count}": "bosses changed outside the program: {count}",
    "Certyfikat – {game}": "Certificate – {game}",
    "Nie można zapisać pliku {name} (sprawdź, czy nie jest otwarty w innym programie).":
        "Cannot save the file {name} (check that it is not open in another program).",
    "Nie udało się zapisać pliku {name}.": "Could not save the file {name}.",
    "{APP_NAME} · {value} · {game} · {value2} · śmierci {deaths} · ": "{APP_NAME} · {value} · {game} · {value2} · deaths {deaths} · ",
    "NIEPODPISANY": "UNSIGNED",
    "DATA WYSTAWIENIA": "DATE OF ISSUE",
    "KOD WERYFIKACYJNY": "VERIFICATION CODE",
    "brak – wersja bez podpisu": "none – unsigned version",
    "Autentyczność sprawdzisz w programie {APP_NAME}: przycisk „Sprawdź certyfikat…”.":
        "You can verify authenticity in {APP_NAME}: the “Verify certificate…” button.",
    "CERTYFIKAT": "CERTIFICATE",
    "Niniejszym poświadcza się zmagania gracza": "This certifies the struggles of player",
    "w grze": "in the game",
    "Niniejszym poświadcza się zmagania w grze": "This certifies the struggles in the game",
    ". Szczegóły w załączniku „Korekty”.": ". Details in the “Adjustments” appendix.",
    "Uwaga – wynik zawiera zmiany: ": "Note – the result contains changes: ",
    "ŚMIERCI ŁĄCZNIE": "TOTAL DEATHS",
    "ŚMIERCI PRZY BOSSACH": "DEATHS TO BOSSES",
    "CZAS POKONANIA BOSSÓW": "TIME TO DEFEAT BOSSES",
    "Pierwszy boss wciąż czeka na pokonanie.": "The first boss is still waiting to be defeated.",
    "POKONANI BOSSOWIE": "DEFEATED BOSSES",
    "  ({count_shown} z {count_defeated} – pełna lista w załączniku)": "  ({count_shown} of {count_defeated} – full list in the appendix)",
    "ZAŁĄCZNIK DO CERTYFIKATU": "CERTIFICATE APPENDIX",
    "{game} – lista bossów": "{game} – boss list",
    "Boss": "Boss",
    "Status": "Status",
    "Śmierci": "Deaths",
    "Czas walki": "Fight time",
    "pokonany": "defeated",
    "w trakcie": "in progress",
    "Kod weryfikacyjny: {value}": "Verification code: {value}",
    "{game} – korekty i zmiany": "{game} – adjustments and changes",
    "Rejestr zmian został zmieniony poza programem albo uszkodzony – wyniku nie da się potwierdzić.":
        "The change log was modified outside the program or damaged – the result cannot be confirmed.",
    "Licznik": "Counter",
    "Dodane ręcznie": "Added manually",
    "Odjęte ręcznie": "Removed manually",
    "Śmierci poza programem": "Deaths outside the program",
    "Czas poza programem": "Time outside the program",
    "Bez historii": "No history",
    " (status zmieniony)": " (status changed)",
    " (lista bossów zmieniona)": " (boss list changed)",
    "„Dodane / odjęte ręcznie” – przyciski i skróty +1/−1 oraz reset w programie. „Poza programem” – zmiana plików "
    "z wynikami (np. w Notatniku). „Bez historii” – wyniki sprzed rejestru zmian albo po jego usunięciu.":
        "“Added / removed manually” – the +1/−1 buttons and hotkeys and the reset in the program. “Outside the "
        "program” – changes to the score files (e.g. in Notepad). “No history” – results from before the change "
        "log or after it was deleted.",

    # results_window.py
    "Czas": "Time",
    "Nr": "No.",
    "Początek": "Start",
    "Wynik": "Result",
    "Kliknij dwukrotnie bossa, aby zobaczyć historię jego prób.": "Double-click a boss to see its attempt history.",
    "Porównuje nazwy bossów w tabeli z listą nazw tej gry i zamienia podobne\n(np. odczytane z błędem) na nazwy "
    "z listy. Przed zmianą pokazuje, co się zmieni.":
        "Compares the boss names in the table with this game's name list and replaces similar ones\n(e.g. "
        "misread ones) with names from the list. Shows what will change before changing anything.",
    "Brak bossów – walki pojawią się tu, gdy włączysz „Śledź walkę z bossem”.":
        "No bosses – fights will appear here once you turn on “Track boss fights”.",
    "Wyniki – {game}": "Results – {game}",
    "<b>Śmierci łącznie: {deaths}</b> &nbsp;·&nbsp; pokonani bossowie: {count_defeated} z {count_rows} "
    "&nbsp;·&nbsp; śmierci przy bossach: {boss_deaths} &nbsp;·&nbsp; czas walk: {total_time}":
        "<b>Total deaths: {deaths}</b> &nbsp;·&nbsp; bosses defeated: {count_defeated} of {count_rows} "
        "&nbsp;·&nbsp; deaths to bosses: {boss_deaths} &nbsp;·&nbsp; fight time: {total_time}",
    "W TRAKCIE (bieżąca walka)": "IN PROGRESS (current fight)",

    # rtss.py
    "tekst przekazany do RTSS": "text sent to RTSS",
    "RTSS nie jest uruchomiony": "RTSS is not running",
    "nieobsługiwana wersja RTSS": "unsupported RTSS version",
    "brak wolnego miejsca na tekst w RTSS": "no free text slot in RTSS",

    # rtss_setup.py
    "W systemie brak programu winget. Zainstaluj RTSS ręcznie ze strony guru3d.com.":
        "winget is not available on this system. Install RTSS manually from guru3d.com.",
    "Instalacja RTSS trwała zbyt długo i została przerwana.": "The RTSS installation took too long and was cancelled.",
    "Instalacja RTSS nie powiodła się (anulowana lub błąd winget). ": "The RTSS installation failed (cancelled or a winget error). ",
    "Nie udało się utworzyć zadania uruchamiającego RTSS (kod {code}).": "Could not create the task that starts RTSS (code {code}).",
    "Anulowano okno uprawnień administratora (UAC).": "The administrator permission (UAC) prompt was cancelled.",
    "Nie można uruchomić {name} (błąd {error}).": "Cannot start {name} (error {error}).",

    # storage.py
    "Nie można zapisać pliku {name}: {exc}": "Cannot save the file {name}: {exc}",
    "Plik {name} był uszkodzony ({exc}). Jego kopię zapisano jako {name2}, a licznik zaczyna od 0.":
        "The file {name} was damaged ({exc}). A copy was saved as {name2}, and the counter starts from 0.",
    "brak pola \"deaths\"": "the \"deaths\" field is missing",
    "pole \"deaths\" nie jest liczbą całkowitą": "the \"deaths\" field is not an integer",
    "pole \"deaths\" jest ujemne": "the \"deaths\" field is negative",

    # template.py
    "Plik {name} nie jest obsługiwanym obrazem.": "The file {name} is not a supported image.",
    "Nie można zakodować zrzutu kalibracji.": "Cannot encode the calibration screenshot.",
    "Rozmiar obrazu wzorca nie zgadza się z zapisanym obszarem.": "The template image size does not match the saved area.",
    "Zaznaczony obszar jest za mały (minimum {MIN_WIDTH}×{MIN_HEIGHT} px). Zaznacz cały napis lub cały fragment "
    "ramki paska.":
        "The selected area is too small (minimum {MIN_WIDTH}×{MIN_HEIGHT} px). Select the whole text or the whole "
        "part of the bar frame.",
    "Zaznaczony obszar jest prawie jednolity. Zaznacz napis lub ramkę paska, a nie samo tło.":
        "The selected area is almost uniform. Select the text or the bar frame, not just the background.",
    "Brak pliku wzorca {name}. Wykonaj kalibrację.": "The template file {name} is missing. Calibrate.",
    "Nie można zakodować obrazu wzorca.": "Cannot encode the template image.",

    # main_window.py – aktualna sesja
    "Aktualna sesja": "Current session",
    "Śledź sesję": "Track session",
    "Sesja zaczyna się, gdy uruchomisz grę, a czas biegnie tylko wtedy, gdy gra jest włączona\n"
    "i jest aktywnym oknem – stoi, gdy gra jest zminimalizowana albo w tle po Alt+Tab\n"
    "(po powrocie do gry czas rusza po ok. 2 s, które też są doliczane).\n"
    "Powrót do gry w ciągu 15 minut (np. po wysypaniu się gry) kontynuuje tę samą sesję.":
        "A session starts when you launch the game, and its time runs only while the game is running\n"
        "and is the active window – it pauses while the game is minimised or in the background after Alt+Tab\n"
        "(after you return to the game the time starts after about 2 s, which are counted too).\n"
        "Returning to the game within 15 minutes (e.g. after a crash) continues the same session.",
    "Przełączaj licznik na uruchomioną grę": "Switch the counter to the running game",
    "Gdy uruchomisz inną grę z listy, licznik sam się na nią przełączy.\n"
    "Ręczny wybór gry w trakcie grania nie jest cofany.":
        "When you launch another game from the list, the counter switches to it by itself.\n"
        "Choosing a game by hand while playing is not undone.",
    "Pokaż sesję na nakładce": "Show session on the overlay",
    "Nakładka i RTSS pokazują śmierci i czas sesji, gdy gra jest uruchomiona.":
        "The overlay and RTSS show the session deaths and time while the game is running.",
    "Stan:": "State:",
    "Śmierci:": "Deaths:",
    "Czas:": "Time:",
    "Uruchomiono grę {name} – licznik przełączył się na nią.": "{name} was launched – the counter switched to it.",
    "Ta gra nie ma jeszcze kalibracji – kliknij „Kalibracja…”, żeby liczyć śmierci.":
        "This game is not calibrated yet – click “Calibration…” to count deaths.",
    "Nie zapisano sesji: {exc}": "The session was not saved: {exc}",
    "Wskaż exe gry": "Choose the game's exe",
    "Programy (*.exe)": "Programs (*.exe)",
    "Zmień exe gry…": "Change game exe…",
    "Wskaż exe gry…": "Choose game exe…",
    "Program nie zna exe tej gry – wskaż go, żeby śledzić sesję.":
        "The program does not know this game's exe – choose it to track the session.",
    "Śledzenie sesji jest wyłączone.": "Session tracking is off.",
    "Program nie wie, jak rozpoznać tę grę – wskaż jej exe.":
        "The program does not know how to recognise this game – choose its exe.",
    "W grze": "In game",
    "Pauza": "Paused",
    "Przerwa": "Break",
    "Nieznana gra": "Unknown game",
    "Wyłączona": "Off",
    "{exe} – czas sesji biegnie.": "{exe} – the session time is running.",
    "Gra w tle ({exe}) – czas sesji stoi.": "Game in the background ({exe}) – the session time is paused.",
    "Gra zamknięta – powrót w ciągu {minutes} min kontynuuje sesję.":
        "Game closed – returning within {minutes} min continues the session.",
    "Czekam na uruchomienie gry.": "Waiting for the game to start.",
    "ostatnia sesja": "last session",

    "Statystyki sesji…": "Session statistics…",
    "Przebieg aktualnej sesji i porównanie wszystkich sesji tej gry.":
        "The course of the current session and a comparison of all sessions of this game.",

    # session_stats.py
    "Sesja": "Session",
    "Śmierci/h": "Deaths/h",
    "Śmierci w kolejnych sesjach": "Deaths in each session",
    "Wszystkie sesje": "All sessions",
    "Statystyki sesji – {game}": "Session statistics – {game}",
    "Brak sesji – uruchom grę, a sesja zacznie się sama.": "No session yet – launch the game and a session starts by itself.",
    "Brak sesji – historia zbiera się od wersji 1.12.0.": "No sessions – the history has been recorded since version 1.12.0.",
    "Sesja {number} (bieżąca)": "Session {number} (current)",
    "Sesja {number}": "Session {number}",
    "Czas gry": "Play time",
    "Śmierci na godzinę": "Deaths per hour",
    "Najdłużej bez śmierci": "Longest without dying",
    "Od ostatniej śmierci": "Since the last death",
    "Sesje": "Sessions",
    "Śmierci łącznie": "Total deaths",
    "Czas gry łącznie": "Total play time",
    "Średnio na sesję": "Average per session",
    "Przebieg sesji": "Session timeline",
    "Przebieg sesji z {when} (zakończona)": "Session from {when} (ended)",
    "Przebieg sesji z {when}": "Session from {when}",
    "{count} śmierci z tej sesji nie ma zapisanego czasu (sprzed zbierania czasów śmierci) – są na początku wykresu.":
        "{count} deaths of this session have no recorded time (from before death times were recorded) – "
        "they are at the start of the chart.",
    "Śmierci w ostatnich {count} sesjach (wszystkie są w tabeli)": "Deaths in the last {count} sessions (all are in the table)",
    "{number} (bieżąca)": "{number} (current)",
    "Czas gry: {time}": "Play time: {time}",
    "Śmierci na godzinę: {value}": "Deaths per hour: {value}",

    # steam_library.py
    "Brak połączenia ze sklepem Steam ({exc}).": "No connection to the Steam store ({exc}).",
    "Nieczytelna odpowiedź sklepu Steam ({exc}).": "Unreadable response from the Steam store ({exc}).",
    "Nie znaleziono Steama na tym komputerze.": "Steam was not found on this computer.",

    # steam_dialog.py
    "tag Souls-like w Steam": "Souls-like tag on Steam",
    "znana gra souls-like": "known souls-like game",
    "inspirowana soulsami": "inspired by Souls",
    "Możliwe souls-like – tag „Souls-like” jest dalej wśród tagów gry. Zaznacz, jeśli gra ma ekran śmierci:":
        "Possible souls-like – the “Souls-like” tag is lower among the game's tags. Select a game if it has a "
        "death screen:",
    "Program czyta listę zainstalowanych gier z plików Steama na tym komputerze. Do sklepu Steam wysyła tylko ich "
    "numery (AppID), żeby sprawdzić tag „Souls-like”.":
        "The program reads the list of installed games from Steam's files on this computer. It sends only their "
        "numbers (AppID) to the Steam store to check the “Souls-like” tag.",
    "Sprawdzanie biblioteki Steam…": "Checking the Steam library…",
    "Dodaj zaznaczone": "Add selected",
    "Anuluj": "Cancel",
    "Zainstalowane gry: {installed}. Souls-like: {sure}, możliwe souls-like: {maybe}.":
        "Installed games: {installed}. Souls-like: {sure}, possible souls-like: {maybe}.",
    "Nie udało się sprawdzić tagów: {error} Użyto wbudowanej listy znanych gier.":
        "Could not check the tags: {error} The built-in list of known games was used.",
    "Zaznacz gry, które mają dostać licznik.": "Select the games that should get a counter.",
    "Brak nowych gier do dodania.": "No new games to add.",
    "{name} – wbudowana w program ({game})": "{name} – built into the program ({game})",
    "{name} – już na liście": "{name} – already on the list",

    # updater.py
    "Nieczytelny numer wersji w wydaniu: {get!r}.": "Unreadable version number in the release: {get!r}.",
    "Nie udało się sprawdzić aktualizacji: {exc}": "Could not check for updates: {exc}",
    "To wydanie nie ma pliku DeathCounter.exe z sumą kontrolną – pobierz je ręcznie.":
        "This release has no DeathCounter.exe with a checksum – download it manually.",
    "Pobieranie przerwane.": "Download cancelled.",
    "Pobrano {done} z {size} bajtów – połączenie zostało przerwane.":
        "Downloaded {done} of {size} bytes – the connection was interrupted.",
    "Suma kontrolna pobranego pliku się nie zgadza – plik jest uszkodzony albo podmieniony.":
        "The checksum of the downloaded file does not match – the file is damaged or was replaced.",
    "Nie udało się pobrać aktualizacji: {exc}": "Could not download the update: {exc}",
    "Nie można podmienić {name}: {exc}": "Cannot replace {name}: {exc}",
    "Nie można zapisać nowej wersji: {exc}": "Cannot save the new version: {exc}",

    # winapi.py
    "Nie udało się przenieść do Kosza (kod {code:#x}). Sprawdź, czy pliki nie są otwarte.":
        "Could not move to the Recycle Bin (code {code:#x}). Check that the files are not open.",

    # worker.py
    "aktywny": "active",
    "zatrzymany": "stopped",
    "brak obrazu": "no image",
    "brak wzorca": "no template",
    "błąd": "error",
    "Nieoczekiwany błąd przy uruchamianiu RTSS: {exc}": "Unexpected error while starting RTSS: {exc}",
    "RTSS nie jest zainstalowany.": "RTSS is not installed.",
    "Instalowanie RTSS (winget)… potwierdź okno uprawnień administratora.":
        "Installing RTSS (winget)… confirm the administrator permission prompt.",
    "RTSS już działa.": "RTSS is already running.",
    "Potwierdź jednorazowo okno uprawnień – potem RTSS będzie startował z licznikiem bez pytania.":
        "Confirm the permission prompt once – after that RTSS will start with the counter without asking.",
    "Uruchamianie RTSS…": "Starting RTSS…",
    "RTSS uruchomiony.": "RTSS started.",
    "Nieoczekiwany błąd detektora: {exc}": "Unexpected detector error: {exc}",
    "Przechwytywanie uruchomione.": "Capture started.",
    "{exc} Ponowna próba za kilka sekund.": "{exc} Retrying in a few seconds.",
    "Błąd przechwytywania obrazu: {exc}": "Screen capture error: {exc}",
    "Rozdzielczość obrazu zmieniła się na {w}×{h}; wzorzec został przeskalowany.":
        "The image resolution changed to {w}×{h}; the template was rescaled.",
    "Brak nowych klatek od {int} s. Sprawdź, czy gra działa na wybranym monitorze.":
        "No new frames for {int} s. Check that the game is running on the selected monitor.",
    "Obraz zamrożony od {int} s.": "Image frozen for {int} s.",
    "Wykrywanie działa.": "Detection is running.",
    "Odczyt nazwy bossa niedostępny: {exc}.": "Boss name reading unavailable: {exc}.",
    "Błąd odczytu nazwy bossa: {exc}": "Boss name reading error: {exc}",
}
