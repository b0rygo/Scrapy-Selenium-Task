## Overview

# UPDATE 11.12.2025

# Analiza Przechwyconych Żądań POST

Po przeanalizowaniu 13 przechwyconych żądań POST potwierdzono, że linki do pobrania dokumentów SI nie są bezpośrednimi adresami URL, lecz wywołują złożoną operację po stronie serwera.

### Wspólne Cechy Wszystkich Żądań

Wszystkie 13 przechwyconych żądań charakteryzują się następującymi stałymi elementami:

- **Adres docelowy (URL)**: Wszystkie żądania są kierowane na ten sam adres strony z wynikami:
  ```
  https://www.handelsregister.de/rp_web/sucheErgebnisse/welcome.xhtml?cid=1
  ```
- **Metoda HTTP**: Wszystkie wykorzystują metodę **POST**.
- **Typ dokumentu**: Wszystkie zawierają stały parametr:
  ```
  'property': 'Global.Dokumentart.SI'
  ```
  który informuje serwer, że użytkownik chce pobrać dokument SI.
- **Nazwa formularza**: Wszystkie żądania są powiązane z formularzem:
  ```
  ergebnissForm
  ```

### Identyfikator Unikalności

Jedynym elementem, który odróżnia żądanie dla jednej firmy od drugiej, jest **unikalny identyfikator komponentu PrimeFaces**.
Jest to para klucz-wartość, gdzie zarówno klucz, jak i wartość mają identyczną, złożoną strukturę:
```
ergebnissForm:selectedSuchErgebnisFormTable:X:j_idt219:6:fade_
```
**Zmienna wartość (X)**: Indeks wiersza w tabeli z wynikami (od 0 do 12).

### Wnioski
To dynamicznie generowane ID jest identyfikatorem wybranego wiersza/firmy w tabeli wyników. System JSF wykorzystuje ten parametr do wewnętrznego powiązania żądania POST z konkretnym rekordem danych po stronie serwera, umożliwiając mu zwrócenie właściwego pliku. Bez tego precyzyjnego indeksu, serwer nie byłby w stanie zidentyfikować, który dokument ma zostać pobrany.

## Przydatne zmienne środowiskowe

- `TARGET_URL` – URL strony (domyślnie handelsregister.de).

## Pobieranie plików XML

**Problem**: Linki z parametrami GET nie działają bezpośrednio - dostajesz błąd 440 (wygasła sesja), ponieważ:
- Wymagają aktywnej sesji (cookies)
- Faktyczny request to POST z parametrami w body, nie GET w URL
- Sesja wygasa po czasie nieaktywności

# UPDATE 10.12.2025
-  scrapowanie metodą "na dwa kroki" (pozyskanie danych przez Selenium i pobieranie przez requests) nie powiodło się, ponieważ strona H&M jest chroniona przez zaawansowany system anty-botowy (Akamai Bot Manager). System ten wiąże sesję nie tylko z ciasteczkami, ale również z unikalnym "odciskiem palca" przeglądarki (TLS Fingerprint) i aktywnym wykonywaniem kodu JavaScript, czego biblioteka requests nie potrafi symulować. W momencie przełączenia się na requests, serwer wykrył brak cech prawdziwej przeglądarki oraz zmianę sygnatury połączenia, przez co natychmiast unieważnił tokeny sesyjne i zablokował dostęp.

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
- Przechwycone requesty są zapisywane w `window._capturedRequests`.
- Zapisuje przechwycone requesty (URL, parametry POST) jako itemy JSON.

## Przydatne zmienne środowiskowe

- `TARGET_URL` – URL strony (domyślnie handelsregister.de).

**Problem**: Linki z parametrami GET nie działają bezpośrednio - dostajesz błąd 440 (wygasła sesja), ponieważ:
- Wymagają aktywnej sesji (cookies)
- Faktyczny request to POST z parametrami w body, nie GET w URL
- Sesja wygasa po czasie nieaktywności (kilku milisekundach )

## Notatki

- Projekt używa **Selenium z JavaScript injection** do przechwytywania requestów sieciowych.
- Scrapy zapisuje wynik do `results/items.json` zgodnie z `FEEDS` w `handelsregister/settings.py`.
- **Rotacja IP przez Mullvad VPN jest wyłączona (zakomentowana)** - zmieniono to ponieważ sprawdzający nie mają dostępu do Mullvada.

