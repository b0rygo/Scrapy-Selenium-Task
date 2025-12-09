## Overview

# UPDATE 09.12.2025
- Zakomentowałem wszelkie użycie Mullvada (rotacji IP) w celach sprawdzenia samego kodu dla dwoch scraperów. 

Projekt zawiera dwa niezależne tryby pracy:
- **SeleniumScraper.py** – samodzielny skrypt uruchamiający przeglądarkę (undetected_chromedriver), wykonujący kroki na handelsregister.de, pobierający pliki XML (SI) do katalogu i analizujący je do jednego pliku JSON.
- **Scrapy** – projekt spidera, który uruchamia wewnętrznie ten sam proces i następnie parsuje XML do itemów i zapisu w JSON.

Katalogi i pliki kluczowe:
- `SeleniumScraper.py` – skrypt standalone (ETAP1 + analiza).
- `handelsregister/` – projekt Scrapy (spider + utils + settings).
- `plikiXMLbySelenium/` – domyślny katalog pobrań XML (z Selenium).
- `plikiXMLbyScrapy/` – domyślny katalog pobrań XML (z Scrapy).
- `results/items.json` (Scrapy) lub `result.json` (Selenium).

## Wymagania

- Python 3.11 (rekomendacja)
- Zależności:
  - `undetected-chromedriver`
  - `selenium`
  - `scrapy`
  - `xmltodict`
  - `pandas`
  - `xmltodict`
  
Instalacja (w aktywnym virtualenv):
```
pip install undetected-chromedriver selenium scrapy xmltodict pandas
```

## Uruchamianie – skrypt Selenium (standalone)

1. (Opcjonalnie) ustaw URL i katalog pobrań:
   - `TARGET_URL` (domyślnie `https://www.handelsregister.de/`)
   - `XML_DIR` (domyślnie `plikiXML`)
2. Uruchom:
```
python SeleniumScraper.py
```
3. Efekty:
   - ETAP1: pobiera pliki SI (XML) do `XML_DIR` (domyślnie `plikiXML`).
   - ETAP2: parsuje wszystkie XML, usuwa prefix `tns:`, wymusza listę `beteiligung`, zapisuje jeden plik JSON (`AllData.json` lub `wszystkie_dane.json` – zależnie od aktualnej konfiguracji w pliku).

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
   - Spider wywołuje ETAP1 (Selenium) wewnątrz `handelsregister/utils.py`, pobiera XML do `download_dir` (domyślnie `plikiXML`).
   - Następnie parsuje wszystkie XML (jak w skrypcie) i zapisuje itemy do `results/items.json` (zdefiniowane w `handelsregister/settings.py` – `FEEDS`).

## Szczegóły działania ETAP1 (Selenium)

Kroki automatyczne (w `SeleniumScraper.py` lub `handelsregister/utils.py`):
1. Otwiera `https://www.handelsregister.de/` (lub `TARGET_URL`).
2. Klik „Normale Suche”.
3. Wybiera „Registerart” = HRB.
4. Wpisuje numer rejestru 25386.
5. Ustawia „Ergebnisse pro Seite” = 100.
6. Klik „Suchen”.
7. Iteracyjnie klika linki SI wg wzorca XPath `//*[@id="ergebnissForm:selectedSuchErgebnisFormTable:{i}:j_idt219:6:fade_"]` aż do braku kolejnych – pobiera wszystkie XML do katalogu `XML_DIR`.
8. Czeka krótko, zamyka driver.

## Szczegóły działania ETAP2 (analiza XML)

- Czyści prefix `tns:`.
- Parsuje `xmltodict.parse(..., force_list={"beteiligung"})`.
- Dodaje `zrodlo_plik`.
- Buduje jeden obiekt JSON: `{"count": <liczba>, "items": [ {...}, ... ]}`.
- Zapis do pliku (`AllData.json`, `wszystkie_dane.json` lub `results/items.json` w przypadku Scrapy FEEDS).

## Przydatne zmienne środowiskowe

- `TARGET_URL` – URL strony (domyślnie handelsregister.de).
- `XML_DIR` – katalog pobrań/odczytu XML (domyślnie `plikiXML`).

## Notatki

- Skrypty używają `undetected_chromedriver` w trybie headless (ustawione). Możesz odkomentować w `utils.py` lub `SeleniumScraper.py`.
- Scrapy zapisuje wynik do `results/items.json` zgodnie z `FEEDS` w `handelsregister/settings.py`.
- Skrypty oba wykorzystują rotacje IP w razie nieudanych prób przy pomocy MullvadVPN.

