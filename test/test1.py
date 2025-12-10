import time
import os
import json
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import StaleElementReferenceException

# --- KONFIGURACJA ---
TARGET_URL = "https://www2.hm.com/pl_pl/on/produkty/view-all.html"
OUTPUT_FILE = "hm_links_with_session.txt"


def build_driver():
    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,800")
    return uc.Chrome(options=options)


def handle_cookies(driver, wait):
    """H&M wymaga akceptacji cookies, inaczej zasłaniają ekran."""
    print("🍪 Szukam banera cookies...")
    try:
        accept_btn = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
        accept_btn.click()
        print("✅ Zaakceptowano cookies.")
        time.sleep(1)
    except Exception:
        print("⚠️ Nie znaleziono banera cookies (może już zaakceptowane).")


def scroll_page(driver):
    """H&M wymaga przewijania, aby załadować produkty (Lazy Loading)."""
    print("📜 Przewijanie strony...")
    for _ in range(3):  # Przewiń 3 razy
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
    driver.execute_script("window.scrollTo(0, 0);")  # Wróć na górę
    time.sleep(1)


def run_scraper():
    driver = None
    try:
        print("🚀 Uruchamianie przeglądarki...")
        driver = build_driver()
        wait = WebDriverWait(driver, 15)

        print(f"🌐 Wchodzenie na: {TARGET_URL}")
        driver.get(TARGET_URL)

        # Obsługa specyficzna dla H&M
        handle_cookies(driver, wait)
        scroll_page(driver)

        # Czekamy na załadowanie produktów
        print("⏳ Oczekiwanie na produkty...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//li//article")))

        # ---------------------------------------------------------
        # EKSTRAKCJA DANYCH SESJI (Dostosowane do H&M)
        # ---------------------------------------------------------
        print(f"📋 Zbieranie danych do pliku: {OUTPUT_FILE}...")

        # 1. VIEWSTATE - H&M tego NIE używa, ale zachowujemy format pliku
        view_state = "BRAK (H&M nie używa technologii JSF ViewState)"

        # 2. COOKIES - H&M używa wielu ciasteczek, pobieramy je wszystkie jako string
        cookies = driver.get_cookies()
        # Tworzymy string w formacie "name=value; name2=value2" (gotowy do nagłówka Cookie)
        cookies_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

        # Pobieramy User-Agent (ważne dla H&M bo mają zabezpieczenia przed botami)
        user_agent = driver.execute_script("return navigator.userAgent;")

        # 3. Znajdź produkty (artykuły)
        # Szukamy struktury: li -> article
        articles = driver.find_elements(By.XPATH, "//li//article")

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            # Nagłówek pliku w formacie z Twojego przykładu
            f.write("# DANE SESJI (Dostosowane do H&M)\n")
            f.write(f"URL={TARGET_URL}\n")
            f.write(f"USER_AGENT={user_agent}\n")  # Dodatkowe, ważne dla H&M
            f.write(f"COOKIES_STRING={cookies_string}\n")  # Zamiast pojedynczego JSESSIONID
            f.write(f"VIEWSTATE={view_state}\n")
            f.write("-" * 100 + "\n")
            f.write("NR | NAZWA_PRODUKTU | LINK (HREF)\n")
            f.write("-" * 100 + "\n")

            count = 0
            processed_urls = set()

            for i, article in enumerate(articles):
                try:
                    # Krok A: Szukamy linku wewnątrz artykułu
                    # Szukamy tagu <a>, który ma href (dowolny, nie tylko productpage, żeby złapać wszystko)
                    try:
                        link_element = article.find_element(By.TAG_NAME, "a")
                        href = link_element.get_attribute("href")
                    except:
                        continue  # Jeśli nie ma linku, to nie produkt

                    # Filtracja duplikatów i pustych linków
                    if not href or href in processed_urls:
                        continue

                    # H&M często ma linki typu 'javascript:void(0)' lub puste - pomijamy je
                    if "http" not in href:
                        continue

                    processed_urls.add(href)

                    # Krok B: Szukamy tytułu (tag <h2>) wewnątrz tego samego artykułu
                    try:
                        title_element = article.find_element(By.TAG_NAME, "h2")
                        product_name = title_element.text.strip().replace("\n", " ")
                    except:
                        product_name = "Brak nazwy"

                    # Zapis
                    f.write(f"{count} | {product_name} | {href}\n")
                    print(f"   ✅ Znaleziono: {product_name}")
                    count += 1

                except StaleElementReferenceException:
                    # Element zniknął przy przewijaniu
                    pass
                except Exception as e:
                    # print(f"Błąd wiersza: {e}")
                    pass

        print("-" * 30)
        print(f"🎉 SUKCES! Zapisano {count} produktów do pliku '{OUTPUT_FILE}'.")
        print(f"👉 Masz teraz listę URLi i ciasteczka potrzebne do ich pobrania.")

    except Exception as e:
        print(f"❌ Wystąpił błąd: {e}")
        if driver:
            driver.save_screenshot("hm_error.png")

    finally:
        if driver:
            print("👋 Zamykanie przeglądarki...")
            driver.quit()


if __name__ == "__main__":
    run_scraper()