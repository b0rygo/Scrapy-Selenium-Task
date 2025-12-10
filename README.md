## Overview

# UPDATE 09.12.2025
- **Rotacja IP przez Mullvad VPN została wyłączona (zakomentowana)** - zmieniono to ponieważ sprawdzający nie mają dostępu do Mullvada. Kod rotacji IP pozostaje w komentarzach w `handelsregister/utils.py` i można go łatwo przywrócić odkomentowując odpowiednie sekcje. 

Projekt zawiera dwa niezależne tryby pracy:
- **SeleniumScraper.py** – samodzielny skrypt uruchamiający przeglądarkę (undetected_chromedriver), wykonujący kroki na handelsregister.de, pobierający pliki XML (SI) do katalogu i analizujący je do jednego pliku JSON.
- **Scrapy** – projekt spidera, który uruchamia wewnętrznie ten sam proces i następnie parsuje XML do itemów i zapisu w JSON.

Katalogi i pliki kluczowe:
- `SeleniumScraper.py` – skrypt standalone (pełna ścieżka scrapowania).
- `handelsregister/` – projekt Scrapy (spider + utils + settings).
- `results/items.json` (Scrapy) lub `result.json` (Selenium) – pliki z zebranymi linkami.

## Wymagania

- Python 3.11 (rekomendacja)
- Zależności:
  - `undetected-chromedriver`
  - `selenium`
  - `scrapy`
  - `xmltodict`
  - `pandas`
  
Instalacja (w aktywnym virtualenv):
```
pip install undetected-chromedriver selenium scrapy xmltodict pandas requests
```

## Uruchamianie – skrypt Selenium (standalone)

1. (Opcjonalnie) ustaw URL:
   - `TARGET_URL` (domyślnie `https://www.handelsregister.de/`)
2. Uruchom:
```
python SeleniumScraper.py
```
3. Efekty:
   - Przechodzi przez pełną ścieżkę: main_page → search_page (input) → search_results.
   - Przechwytuje POST requesty z onclick przez JavaScript injection (BEZ faktycznego pobierania plików).
   - Zbiera wszystkie linki z wyników wyszukiwania wraz z przechwyconymi requestami.
   - Zapisuje jako itemy w formacie JSON do `result.json`.

## Uruchamianie – Scrapy

1. Upewnij się, że zależności są zainstalowane (jak wyżej).
2. Domyślne uruchomienie spidera:
```
scrapy crawl handels_spider
```
3. Parametry opcjonalne:
   - argumenty: `scrapy crawl handels_spider -a target_url=... -a download_dir=plikiXML`
   - zmienne środowiskowe: `TARGET_URL`, `XML_DIR`
4. Efekty:
   - Spider wywołuje scrapowanie (Selenium) wewnątrz `handelsregister/utils.py`.
   - Przechodzi przez pełną ścieżkę: main_page → search_page (input) → search_results.
   - Przechwytuje POST requesty z onclick przez JavaScript injection (BEZ faktycznego pobierania plików).
   - Zbiera wszystkie linki z wyników wyszukiwania wraz z przechwyconymi requestami.
   - Zapisuje jako itemy do `results/items.json`.

## Szczegóły działania (Pełna ścieżka scrapowania)

Kroki automatyczne (w `SeleniumScraper.py` lub `handelsregister/utils.py`):
1. **main_page**: Otwiera `https://www.handelsregister.de/` (lub `TARGET_URL`).
2. **search_page**: Przechodzi do "Normale Suche" (formularz wyszukiwania).
3. **input**: Wypełnia formularz:
   - Wybiera „Registerart” = HRB.
   - Wpisuje numer rejestru 25386.
   - Wybiera z dostepnych miast na alle(tak jak podane w poleceniu)
   - Ustawia „Ergebnisse pro Seite” = 100.
4. **search_request**: Klik „Suchen” (wysyła request wyszukiwania z danymi wejściowymi).
5. **search_results**: Zbiera wszystkie linki z wyników wyszukiwania:
   - Iteruje po wszystkich wierszach tabeli wyników.
   - Dla każdego wiersza zbiera wszystkie dostępne linki (href, text, title).
   - Zapisuje jako itemy w formacie JSON: `{"count": <liczba>, "items": [{"row_number": N, "links": [...]}, ...]}`.
6. Zamyka driver.

**Ważne**: 
- Projekt nie pobiera plików XML, tylko przechwytuje POST requesty z onclick (anulowane przed pobraniem).
- Używa JavaScript injection do przechwytywania XMLHttpRequest i PrimeFaces.addSubmitParam PRZED faktycznym wysłaniem requestu (podobne do Filter/UrlHistory po stronie serwera).
- Przechwycone requesty są zapisywane w `window._capturedRequests` (podobne do `UrlHistory.store`).
- Zapisuje przechwycone requesty (URL, parametry POST) jako itemy JSON.

## Przydatne zmienne środowiskowe

- `TARGET_URL` – URL strony (domyślnie handelsregister.de).

## Pobieranie plików XML

**Problem**: Linki z parametrami GET nie działają bezpośrednio - dostajesz błąd 440 (wygasła sesja), ponieważ:
- Wymagają aktywnej sesji (cookies)
- Faktyczny request to POST z parametrami w body, nie GET w URL
- Sesja wygasa po czasie nieaktywności

**Rozwiązanie**: 
1. `SeleniumScraper.py` automatycznie zapisuje cookies z aktywnej sesji do `session_cookies.json`
2. Użyj funkcji `download_file_with_session()` z modułu `SeleniumScraper` do pobierania plików:

```python
from SeleniumScraper import download_file_with_session

post_url = "https://www.handelsregister.de/rp_web/sucheErgebnisse/welcome.xhtml"
post_params = {
    "ergebnissForm:selectedSuchErgebnisFormTable:0:j_idt222:1:fade_": "ergebnissForm:selectedSuchErgebnisFormTable:0:j_idt222:1:fade_",
    "property": "Global.Dokumentart.CD"
}
download_file_with_session(post_url, post_params, "pobrany_plik.xml")
```

3. Lub użyj skryptu pomocniczego `download_files.py` do pobrania wszystkich plików z `result.json`:

```bash
python download_files.py
```

## Notatki

- Projekt używa **Selenium z JavaScript injection** do przechwytywania requestów sieciowych.
- JavaScript injection przechwytuje `XMLHttpRequest.send()` i `PrimeFaces.addSubmitParam()` PRZED faktycznym wysłaniem requestu (podobne do Filter/UrlHistory po stronie serwera).
- Przechwycone requesty są anulowane przez `xhr.abort()` - request NIE trafia do serwera.
- **Cookies z sesji są zapisywane** do `session_cookies.json` i mogą być użyte do późniejszego pobierania plików przez POST request.
- Scrapy zapisuje wynik do `results/items.json` zgodnie z `FEEDS` w `handelsregister/settings.py`.
- **Rotacja IP przez Mullvad VPN jest wyłączona (zakomentowana)** - zmieniono to ponieważ sprawdzający nie mają dostępu do Mullvada.

