import time
import os
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

# --- KONFIGURACJA WYSZUKIWANIA ---
SEARCH_NUMBER = "25386"
SEARCH_TYPE = "HRB"  # Opcje: HRA, HRB, GnR, PR, VR
SEARCH_TOWN = "alle"  # "alle" wybiera wszystkie sądy
OUTPUT_FILE = "si_links1.txt"


def build_driver():
    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,800")
    # options.add_argument("--headless") # Odkomentuj, jeśli nie chcesz widzieć okna
    return uc.Chrome(options=options)


def wait_for_loading_gone(driver, timeout=15):
    """Czeka aż znikną wszelkie loadery PrimeFaces."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "ui-icon-loading"))
        )
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.ID, "j_idt15:statusDialog"))
        )
    except Exception:
        pass  # Zakładamy, że loadera już nie ma


def run_scraper():
    driver = None
    try:
        print("🚀 Uruchamianie przeglądarki...")
        driver = build_driver()
        wait = WebDriverWait(driver, 15)

        # 1. Wejście na stronę startową
        url = "https://www.handelsregister.de/rp_web/welcome.xhtml"
        print(f"🌐 Wchodzenie na: {url}")
        driver.get(url)
        wait_for_loading_gone(driver)

        # 2. Przejście do wyszukiwania
        print("🔍 Klikanie 'Normale Suche'...")
        try:
            normale_suche = wait.until(EC.element_to_be_clickable((By.ID, "naviForm:normaleSucheLink")))
            normale_suche.click()
        except TimeoutException:
            print("⚠️ Nie znaleziono linku w menu, próbuję przycisk na środku...")
            # Czasami układ strony jest inny, np. wielki przycisk na środku
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'Normale Suche')]")))
            btn.click()

        wait_for_loading_gone(driver)

        # 3. Wypełnianie formularza
        print("📝 Wypełnianie formularza...")

        # A) Typ rejestru (HRB)
        # Klikamy label, żeby upewnić się że radio button zadziała
        try:
            register_label = wait.until(EC.element_to_be_clickable((By.ID, "form:registerArt_label")))
            register_label.click()
            time.sleep(0.5)
            hrb_option = wait.until(EC.element_to_be_clickable((By.XPATH, f"//li[contains(text(), '{SEARCH_TYPE}')]")))
            hrb_option.click()
        except Exception as e:
            print(f"⚠️ Problem z wyborem typu rejestru: {e}")

        wait_for_loading_gone(driver)

        # B) Numer (25386)
        register_input = wait.until(EC.presence_of_element_located((By.ID, "form:registerNummer")))
        register_input.clear()
        register_input.send_keys(SEARCH_NUMBER)

        # C) Sąd (alle)
        # To jest dropdown PrimeFaces -> klikamy Label, potem Element z listy
        register_gericht_label = wait.until(EC.element_to_be_clickable((By.ID, "form:registergericht_label")))
        register_gericht_label.click()
        time.sleep(1)  # Czas na animację rozwinięcia listy

        # Szukamy opcji "alle" (lub innej zdefiniowanej w SEARCH_TOWN)
        town_option = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//ul[@id='form:registergericht_items']//li[@data-label='{SEARCH_TOWN}']")))
        town_option.click()

        wait_for_loading_gone(driver)
        time.sleep(0.5)

        try:
            per_page_label = driver.find_element(By.ID, "form:ergebnisseProSeite_label")
            per_page_label.click()
            per_page_100 = wait.until(EC.element_to_be_clickable((By.XPATH, "//li[contains(@data-label, '100')]")))
            per_page_100.click()
            wait_for_loading_gone(driver)
        except Exception:
            print("⚠️ Nie udało się zmienić liczby wyników na 100, zostawiam domyślną.")

        # 4. Kliknięcie SZUKAJ
        print("🚀 Klikanie 'Suchen'...")
        suche_btn = driver.find_element(By.ID, "form:btnSuche")
        # Używamy JS click, bo czasem element jest przesłonięty
        driver.execute_script("arguments[0].click();", suche_btn)

        # Czekamy na pojawienie się tabeli wyników
        print("⏳ Oczekiwanie na wyniki...")
        wait.until(EC.presence_of_element_located((By.ID, "ergebnissForm:selectedSuchErgebnisFormTable_data")))
        wait_for_loading_gone(driver)

        # ---------------------------------------------------------
        # EKSTRAKCJA DANYCH DO PLIKU TXT
        # ---------------------------------------------------------
        print(f"📋 Zbieranie linków SI do pliku: {OUTPUT_FILE}...")

        # 1. Pobierz ViewState (Kluczowe!)
        try:
            view_state_element = driver.find_element(By.NAME, "javax.faces.ViewState")
            view_state = view_state_element.get_attribute("value")
        except:
            view_state = "BRAK_VIEWSTATE"
            print("❌ BŁĄD: Nie znaleziono javax.faces.ViewState!")

        # 2. Pobierz Cookies (Dla JSESSIONID)
        cookies = driver.get_cookies()
        jsessionid = next((c['value'] for c in cookies if c['name'] == 'JSESSIONID'), 'BRAK')

        # 3. Znajdź wiersze
        rows = driver.find_elements(By.XPATH, "//tbody[contains(@id, 'selectedSuchErgebnisFormTable_data')]/tr")

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            # Nagłówek pliku z danymi sesji
            f.write("# DANE DO ŻĄDANIA POST (Requests/Curl)\n")
            f.write(f"URL=https://www.handelsregister.de/rp_web/sucheErgebnisse/welcome.xhtml\n")
            f.write(f"JSESSIONID={jsessionid}\n")
            f.write(f"VIEWSTATE={view_state}\n")
            f.write("-" * 80 + "\n")
            f.write("NR | FIRMA | ID_ELEMENTU_SI\n")
            f.write("-" * 80 + "\n")

            count = 0
            for i, row in enumerate(rows):
                try:
                    # Spróbuj pobrać nazwę firmy (zazwyczaj 2. kolumna td)
                    try:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        # Format tabeli: [0] akcje, [1] firma, [2] siedziba... (może się różnić)
                        if len(cols) > 2:
                            # Szukamy tekstu w kolumnie, która wygląda na nazwę firmy
                            company_name = cols[1].text.strip().replace("\n", " ")
                        else:
                            company_name = "Nieznana"
                    except:
                        company_name = "Błąd odczytu"

                    # Szukamy linku SI w tym wierszu
                    # Szukamy <a> który ma w onclick tekst 'Global.Dokumentart.SI'
                    si_link = row.find_element(By.XPATH, ".//a[contains(@onclick, 'Global.Dokumentart.SI')]")

                    # Pobieramy ID
                    si_id = si_link.get_attribute("id")

                    if si_id:
                        f.write(f"{i} | {company_name} | {si_id}\n")
                        print(f"   ✅ Znaleziono: {company_name}")
                        count += 1

                except Exception as e:
                    # To normalne, jeśli wiersz nie ma dokumentu SI lub jest pusty
                    pass

        print("-" * 30)
        print(f"🎉 SUKCES! Zapisano {count} linków do pliku '{OUTPUT_FILE}'.")
        print(f"👉 Możesz teraz użyć tych ID i ViewState, aby pobrać pliki (póki sesja jest aktywna).")

        # Opcjonalnie: Czekaj chwilę, żebyś zdążył zobaczyć efekt
        # time.sleep(5)

    except Exception as e:
        print(f"❌ Wystąpił błąd: {e}")
        if driver:
            driver.save_screenshot("error_screenshot.png")
            print("📸 Zapisano zrzut ekranu błędu.")

    finally:
        if driver:
            print("👋 Zamykanie przeglądarki...")
            driver.quit()


if __name__ == "__main__":
    run_scraper()