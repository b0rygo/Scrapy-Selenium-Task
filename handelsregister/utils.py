import os
import random
import time
from typing import Optional

import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# # Lista serwerów Mullvad
# FI_SERVERS = [
#     "de-ber-wg-001",
#     "de-ber-wg-002",
#     "de-ber-wg-003",
#     "de-ber-wg-004",
#     "de-ber-wg-005",
#     "de-ber-wg-006",
#     "de-ber-wg-007",
#     "de-ber-wg-008",
# ]
#
# # Zmienna do pamiętania ostatniego serwera
# current_server = None


def build_driver() -> uc.Chrome:
    download_dir = os.path.join(os.getcwd(), "plikiXMLbyScrapy")
    os.makedirs(download_dir, exist_ok=True)

    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,720")
    options.add_argument("--headless")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )

    driver = uc.Chrome(options=options)
    try:
        driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": download_dir},
        )
    except Exception:
        pass
    return driver


def shutdown_driver(driver: Optional[uc.Chrome]) -> None:
    if not driver:
        return
    try:
        driver.quit()
    except Exception as e:
        print(f"driver.quit() warning: {e}")
    try:
        driver.__del__ = lambda *_, **__: None  # type: ignore[attr-defined]
    except Exception:
        pass


# def change_ip() -> None:
#     """Zmienia IP przez Mullvad, unikając powtórzenia tego samego serwera."""
#     global current_server  # Odwołujemy się do zmiennej globalnej
#     print("\n🌍 Zmieniam IP i czyszczę połączenie...")
#     try:
#         os.system("mullvad disconnect")
#         time.sleep(2)
#
#         # Tworzymy listę dostępnych serwerów z wyłączeniem tego, który jest aktualnie używany
#         available_servers = [s for s in FI_SERVERS if s != current_server]
#
#         # Zabezpieczenie na wypadek gdyby lista była pusta (choć przy tylu serwerach to niemożliwe)
#         if not available_servers:
#             available_servers = FI_SERVERS
#
#         # Losujemy z przefiltrowanej listy
#         new_server = random.choice(available_servers)
#
#         # Aktualizujemy obecny serwer
#         current_server = new_server
#
#         print(f"➡️ Wybrano nowy serwer: {new_server}")
#         os.system(f"mullvad relay set location {new_server}")
#         os.system("mullvad connect")
#         time.sleep(8)  # Czas na złapanie nowego IP
#
#     except Exception as e:
#         print(f"⚠️ Błąd VPN: {e}")


def run_etap1_scrape(target_url: str, download_dir: str, max_retries: int = 3) -> str:
    """Uruchamia scrapowanie z automatyczną zmianą IP przy błędach."""
    # attempts = 0
    # while attempts < max_retries:
    driver = None
    try:
        driver = build_driver()
        driver.get(target_url)

        wait = WebDriverWait(driver, 15)
        print("ETAP1 - NORMAL SUCHE")
        normale_suche = wait.until(
            EC.element_to_be_clickable((By.ID, "naviForm:normaleSucheLink"))
        )
        normale_suche.click()
        time.sleep(2)
        print("ETAP2 - WYBOR Z FORMULARZA")

        register_label = wait.until(
            EC.element_to_be_clickable((By.ID, "form:registerArt_label"))
        )
        register_label.click()
        time.sleep(2)
        hrb_option = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                        "//li[@data-label='HRB' or normalize-space(text())='HRB']",
                )
            )
        )
        hrb_option.click()
        time.sleep(2)

        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            WebDriverWait(driver, 5).until(
                EC.invisibility_of_element_located((By.ID, "form:registerArt_panel"))
            )
        except Exception:
            driver.execute_script("document.body.click();")

        register_input = wait.until(
            EC.element_to_be_clickable((By.ID, "form:registerNummer"))
        )
        register_input.clear()
        register_input.send_keys("25386")
        time.sleep(2)

        per_page_label = wait.until(
            EC.element_to_be_clickable((By.ID, "form:ergebnisseProSeite_label"))
        )
        per_page_label.click()
        time.sleep(2)
        per_page_100 = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//li[@data-label='100' or @id='form:ergebnisseProSeite_3']",
                )
            )
        )
        per_page_100.click()

        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            WebDriverWait(driver, 5).until(
                EC.invisibility_of_element_located(
                    (By.ID, "form:ergebnisseProSeite_panel")
                )
            )
        except Exception:
            driver.execute_script("document.body.click();")

        suche_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "form:btnSuche"))
        )
        try:
            suche_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", suche_btn)

        print("ETAP3 - POBIERANIE PLIKOW")
        i = 0
        while True:
            xpath = (
                f'//*[@id="ergebnissForm:selectedSuchErgebnisFormTable:{i}:j_idt219:6:fade_"]'
            )
            try:
                link = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
            except TimeoutException:
                break
            try:
                link.click()
            except Exception:
                driver.execute_script("arguments[0].click();", link)
            time.sleep(1)
            i += 1
            print("POBIERANIE PLIKU nr:", i)

        time.sleep(5)
            # Sukces - kończymy
        print("SCRAPOWANIE ZAKONCZONE - SUKCES")
        shutdown_driver(driver)
        return download_dir

    except Exception as e:
        print(f"❌ Błąd podczas scrapowania: {e}")
        shutdown_driver(driver)
            
            # # Jeśli to nie ostatnia próba, zmień IP i spróbuj ponownie
            # if attempts < max_retries - 1:
            #     change_ip()
            # attempts += 1
    
    print("⚠️ Wszystkie próby zakończyły się niepowodzeniem.")
    return download_dir

