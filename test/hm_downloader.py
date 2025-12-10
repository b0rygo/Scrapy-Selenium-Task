import requests
import os
import time

INPUT_FILE = "hm_links_with_session.txt"
DOWNLOAD_DIR = "../pobrane_produkty_hm"


def clean_filename(text):
    """Czyści nazwę pliku z niedozwolonych znaków."""
    return "".join([c for c in text if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()


def parse_txt_file(filepath):
    """Parsuje plik tekstowy z danymi sesji i listą produktów."""
    data = {
        "user_agent": None,
        "cookies_string": None,
        "items": []
    }

    if not os.path.exists(filepath):
        print(f"❌ Nie znaleziono pliku: {filepath}")
        return data

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue

            # Pobieranie nagłówków sesji
            if line.startswith("USER_AGENT="):
                data["user_agent"] = line.split("=", 1)[1]
            elif line.startswith("COOKIES_STRING="):
                data["cookies_string"] = line.split("=", 1)[1]

            # Pobieranie produktów (ignorujemy linie komentarzy i nagłówków tabeli)
            elif "|" in line and "NR |" not in line and not line.startswith("-") and not line.startswith("#"):
                parts = line.split("|")
                if len(parts) >= 3:
                    item = {
                        "nr": parts[0].strip(),
                        "nazwa": parts[1].strip(),
                        "link": parts[2].strip()
                    }
                    data["items"].append(item)
    return data


def download_hm_page(session, item, user_agent, cookies_string):
    url = item['link']

    # --- KLUCZOWE: Pełne nagłówki udające Chrome ---
    # H&M sprawdza te nagłówki (Sec-Fetch, Upgrade-Insecure itp.)
    headers = {
        'Host': 'www2.hm.com',
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www2.hm.com/pl_pl/on/produkty/view-all.html',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        # Ciasteczka przekazujemy ręcznie w nagłówku
        'Cookie': cookies_string
    }

    print(f"📥 Pobieranie [{item['nr']}]: {item['nazwa']}...")

    try:
        # Używamy session.get zamiast requests.get dla lepszego zarządzania połączeniem
        response = session.get(url, headers=headers, timeout=15)

        # Obsługa kodów błędów
        if response.status_code == 200:
            # Sprawdzenie czy nie dostaliśmy strony z blokadą
            if "Access Denied" in response.text or "Incapsula" in response.text or "Pardon Our Interruption" in response.text:
                print(f"❌ BLOKADA ANTY-BOTOWA (Access Denied). Twoje ciasteczka mogły wygasnąć lub H&M wykrył skrypt.")
                return False

            safe_name = clean_filename(item['nazwa'])
            # Jeśli nazwa jest pusta, użyj numeru
            if not safe_name: safe_name = "produkt"

            filename = f"{item['nr']}_{safe_name}.html"
            filepath = os.path.join(DOWNLOAD_DIR, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(response.text)

            print(f"   ✅ Zapisano: {filename}")
            return True

        elif response.status_code == 403:
            print(f"❌ Błąd 403 (Forbidden): Serwer odrzucił dostęp. Ciasteczka Akamai wygasły.")
            return False
        elif response.status_code == 404:
            print(f"⚠️ Błąd 404: Produkt nie istnieje.")
            return True  # Nie przerywamy pętli dla 404
        else:
            print(f"❌ Błąd HTTP: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Wyjątek połączenia: {e}")
        return False


def main():
    # Tworzenie folderu
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    # 1. Wczytanie danych
    data = parse_txt_file(INPUT_FILE)

    if not data["user_agent"] or not data["cookies_string"]:
        print("❌ Błąd parsowania: Brak USER_AGENT lub COOKIES_STRING w pliku wejściowym.")
        print("Upewnij się, że plik txt został wygenerowany poprawnie.")
        return

    if not data["items"]:
        print("⚠️ Brak produktów do pobrania w pliku (sekcja z linkami jest pusta).")
        return

    print(f"Znaleziono {len(data['items'])} produktów. Rozpoczynam pobieranie...")

    # Tworzymy sesję requests dla wydajności
    session = requests.Session()

    # 2. Pętla pobierania
    for item in data["items"]:
        success = download_hm_page(session, item, data["user_agent"], data["cookies_string"])

        if not success:
            # Jeśli dostaniemy blokadę (403/Access Denied), nie ma sensu męczyć serwera dalej
            print("\n🛑 PRZERYWANIE SKRYPTU.")
            print("H&M zablokował połączenie. Musisz wygenerować NOWE ciasteczka (uruchom skrypt Selenium ponownie).")
            print("Wskazówka: Ciasteczka H&M (Akamai) wygasają bardzo szybko (kilka minut).")
            break

        # Pauza - H&M jest wrażliwy na szybkość
        time.sleep(3)

    print("\n🏁 Koniec.")


if __name__ == "__main__":
    main()