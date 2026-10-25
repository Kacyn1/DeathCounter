# Wkład w rozwój Death Counter by MK

Dziękuję za chęć pomocy! Program jest wolnym oprogramowaniem na licencji
[GNU GPL v3](LICENSE) (GPL-3.0-only).

## Zgłoszenia błędów i pomysły

Błędy i pomysły zgłaszaj w zakładce **Issues** repozytorium. Pomocne są: wersja programu (okno
„O programie”), gra, opis kroków i zrzut ekranu (np. okna programu z sekcją „Stan”).

## Pull requesty

Wysyłając pull request albo inną propozycję zmian w kodzie, grafice lub dokumentacji (dalej: „wkład”),
potwierdzasz, że:

1. jesteś autorem wkładu albo masz prawo go przekazać, i nie narusza on praw osób trzecich;
2. udostępniasz wkład na licencji GNU GPL v3, tak jak resztę programu;
3. dodatkowo udzielasz Mateuszowi Kacynie (autorowi programu) nieodpłatnej, niewyłącznej,
   nieodwołalnej i nieograniczonej w czasie ani terytorialnie licencji na korzystanie z wkładu na
   wszystkich polach eksploatacji – także na udostępnianie programu z Twoim wkładem na innej licencji
   niż GPL v3 – z prawem udzielania dalszych licencji. Dzięki temu autor może w przyszłości zmienić
   licencję kolejnych wersji programu bez zbierania zgód od każdej osoby, która pomogła.

Jeśli wkład jest większy (np. nowa funkcja), autor może poprosić o potwierdzenie powyższych zasad
w formie pisemnej.

## Zasady techniczne

- Przed wysłaniem zmian uruchom testy: `.\.venv\Scripts\python.exe -m pytest -q`.
- Na macOS działa tryb deweloperski: interfejs programu bez części z Windows (przechwytywanie obrazu, OCR,
  nakładka nad grą, globalne skróty, RTSS). Kalibrację można sprawdzać na zrzutach wczytanych z pliku.
  `./uruchom-mac.sh` uruchamia program, a `./uruchom-mac.sh test` – testy (pierwszy raz tworzy `.venv-mac`
  przez [uv](https://docs.astral.sh/uv/)). Testy zależne od Windows są wtedy pomijane – pełny zestaw uruchamia
  GitHub Actions (`.github/workflows/build.yml`) przy każdym pushu na `main`/`dev` i pull requeście.
- Gałęzie: `main` – wersja wydana (z niej powstają tagi i release'y), `dev` – zmiany przed wydaniem.
  Nowe zmiany: gałąź od `dev` → pull request do `dev`; wydanie: pull request `dev` → `main`, potem tag `v…`.
- Zachowaj styl istniejącego kodu: komentarze i komunikaty po polsku, logika bez Qt tam, gdzie się da
  (łatwiej ją testować).
- Każdy tekst widoczny dla użytkownika opakuj w `tr("…")` (zmienne części jako pola: `tr("Śmierci: {n}", n=5)`),
  a stałe na poziomie modułu w `N_("…")`, i dopisz tłumaczenie do `deathcounter/lang_en.py`. Test
  `tests/test_i18n.py` wskaże teksty bez tłumaczenia.
- Nie dołączaj pliku `deathcounter/_signing_key.py` ani danych z folderu `games/`.
