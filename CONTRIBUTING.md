# Wkład w rozwój Death Counter by MK

Dziękuję za chęć pomocy! Program jest objęty licencją zastrzeżoną ([LICENSE](LICENSE)), więc propozycje
zmian przyjmuję na poniższych zasadach.

## Zgłoszenia błędów i pomysły

Błędy i pomysły zgłaszaj w zakładce **Issues** repozytorium. Pomocne są: wersja programu, gra, opis kroków
i zrzut ekranu (np. okna programu z sekcją „Stan”).

## Pull requesty

Wysyłając pull request albo inną propozycję zmian w kodzie, grafice lub dokumentacji (dalej: „wkład”),
potwierdzasz, że:

1. jesteś autorem wkładu albo masz prawo go przekazać, i nie narusza on praw osób trzecich;
2. udzielasz Mateuszowi Kacynie (Autorowi programu) nieodpłatnej, niewyłącznej, nieodwołalnej
   i nieograniczonej w czasie ani terytorialnie licencji na korzystanie z wkładu na wszystkich polach
   eksploatacji – w tym na jego zmienianie, łączenie z programem, rozpowszechnianie, zastosowania
   komercyjne oraz udostępnianie programu na dowolnej, także innej niż obecna, licencji – z prawem
   udzielania dalszych licencji;
3. nie oczekujesz wynagrodzenia za wkład.

Jeśli wkład jest większy (np. nowa funkcja), Autor może poprosić o potwierdzenie powyższych zasad
w formie pisemnej.

## Zasady techniczne

- Przed wysłaniem zmian uruchom testy: `.\.venv\Scripts\python.exe -m pytest -q`.
- Zachowaj styl istniejącego kodu: komentarze i komunikaty po polsku, logika bez Qt tam, gdzie się da
  (łatwiej ją testować).
- Nie dołączaj pliku `deathcounter/_signing_key.py` ani danych z folderu `games/`.
