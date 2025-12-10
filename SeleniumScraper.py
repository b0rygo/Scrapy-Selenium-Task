import json
import os
import re
import time
from typing import Optional, Dict, Any
from urllib.parse import unquote

import requests
import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SEARCH_NUMBER = "25386"
SEARCH_TYPE = "HRB"
SEARCH_TOWN = "alle"
OUTPUT_JSON = "result.json"

_captured_requests = []

def build_driver() -> uc.Chrome:
    """Konfiguracja sterownika Chrome - TYLKO do przechwytywania requestów, NIE pobiera plików."""
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,720")
    #options.add_argument("--headless")  # Odkomentuj dla trybu bezokienkowego

    driver = uc.Chrome(options=options)

    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    try:
        driver.execute_cdp_cmd("Network.enable", {})
    except Exception:
        pass

    return driver

def wait_for_loading_gone(driver, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "ui-icon-loading"))
        )
        # Czasami jest też blokada całego ekranu
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.ID, "j_idt15:statusDialog"))
        )
    except Exception:
        pass  # Jeśli nie znaleziono loadera, to znaczy że go nie ma, idziemy dalej


def inject_request_interceptor(driver):
    """
    Wstrzykuje JavaScript do przechwytywania PrimeFaces.addSubmitParam i XMLHttpRequest.
    Przechwytuje parametry PRZED faktycznym wysłaniem requestu (podobne do Filter po stronie serwera).
    """
    interceptor_script = """
    (function() {
        window._capturedRequests = window._capturedRequests || [];
        
        // Przechwytujemy PrimeFaces.addSubmitParam
        if (window.PrimeFaces && window.PrimeFaces.addSubmitParam) {
            const originalAddSubmitParam = window.PrimeFaces.addSubmitParam;
            window.PrimeFaces.addSubmitParam = function(formId, params) {
                // Zapisujemy parametry przed faktycznym submitem
                const capturedData = {
                    formId: formId,
                    params: params,
                    url: window.location.href.split('#')[0],
                    timestamp: new Date().toISOString()
                };
                window._capturedRequests.push(capturedData);
                
                // Wywołujemy oryginalną funkcję (żeby strona działała normalnie)
                return originalAddSubmitParam.apply(this, arguments);
            };
        }
        
        const originalXHROpen = XMLHttpRequest.prototype.open;
        const originalXHRSend = XMLHttpRequest.prototype.send;
        
        XMLHttpRequest.prototype.open = function(method, url, async, user, password) {
            this._interceptedMethod = method;
            this._interceptedUrl = url;
            return originalXHROpen.apply(this, arguments);
        };
        
        XMLHttpRequest.prototype.send = function(data) {
            // Sprawdzamy czy to POST request do handelsregister.de
            if (this._interceptedMethod === 'POST' && 
                this._interceptedUrl && 
                this._interceptedUrl.includes('handelsregister.de')) {
                
                // Parsujemy post data
                let postParams = {};
                if (data) {
                    const params = data.split('&');
                    for (let param of params) {
                        if (param.includes('=')) {
                            const [key, value] = param.split('=');
                            try {
                                postParams[decodeURIComponent(key)] = decodeURIComponent(value);
                            } catch(e) {
                                postParams[key] = value;
                            }
                        }
                    }
                }
                
                // Zapisujemy przechwycony request
                const capturedRequest = {
                    url: this._interceptedUrl,
                    method: this._interceptedMethod,
                    post_data: data || '',
                    post_parameters: postParams,
                    headers: {},
                    timestamp: new Date().toISOString()
                };
                
                window._capturedRequests.push(capturedRequest);
                
                this.abort();
                return;
            }
            
            return originalXHRSend.apply(this, arguments);
        };
        
        if (window.fetch) {
            const originalFetch = window.fetch;
            window.fetch = function(url, options) {
                if (options && options.method === 'POST' && 
                    url && url.includes('handelsregister.de')) {
                    
                    // Sprawdzamy czy to request dla SI
                    const isSIRequest = options.body && options.body.includes('Global.Dokumentart.SI');
                    
                    if (isSIRequest) {
                        let postParams = {};
                        if (options.body) {
                            const params = options.body.split('&');
                            for (let param of params) {
                                if (param.includes('=')) {
                                    const [key, value] = param.split('=');
                                    try {
                                        postParams[decodeURIComponent(key)] = decodeURIComponent(value);
                                    } catch(e) {
                                        postParams[key] = value;
                                    }
                                }
                            }
                        }
                        
                        const capturedRequest = {
                            url: url,
                            method: 'POST',
                            post_data: options.body || '',
                            post_parameters: postParams,
                            headers: options.headers || {},
                            timestamp: new Date().toISOString(),
                            document_type: "SI"
                        };
                        
                        window._capturedRequests.push(capturedRequest);
                        
                        // Anulujemy request
                        return Promise.reject(new Error('Request intercepted and aborted'));
                    }
                }
                
                return originalFetch.apply(this, arguments);
            };
        }
    })();
    """
    
    try:
        driver.execute_script(interceptor_script)
    except Exception as e:
        print(f"⚠️ Błąd przy wstrzykiwaniu interceptor: {e}")


def get_captured_requests(driver) -> list:
    """Pobiera przechwycone requesty z JavaScript (podobne do UrlHistory.getStore())."""
    try:
        captured = driver.execute_script("return window._capturedRequests || [];")
        return captured if captured else []
    except Exception:
        return []


def extract_params_from_onclick(onclick: str, link_id: str, current_url: str) -> Optional[dict]:
    """
    Wyciąga parametry POST z onclick BEZ wykonywania kliknięcia.
    NIE KLIKA - tylko parsuje JavaScript z onclick.
    Zwraca dict z URL i parametrami POST.
    """
    try:
        if not onclick or "PrimeFaces" not in onclick or "Global.Dokumentart.SI" not in onclick:
            return None
        
        # Wyciągamy form name z onclick
        form_match = re.search(r"submit\(['\"]([^'\"]+)['\"]\)", onclick)
        form_name = form_match.group(1) if form_match else "ergebnissForm"
        
        # Budujemy słownik parametrów POST na podstawie onclick
        post_params = {}
        
        # Wyciągamy wszystkie parametry z onclick (wszystkie pary key:value)
        all_params_match = re.findall(r"'([^']+)':\s*'([^']*)'", onclick)
        for key, value in all_params_match:
            # Usuwamy spacje z klucza (czasami jest spacja po dwukropku)
            key = key.strip()
            post_params[key] = value
        
        # Tworzymy dict z parametrami requestu
        return {
            "url": current_url.split("#")[0],
            "method": "POST",
            "post_data": "&".join([f"{k}={v}" for k, v in post_params.items()]),
            "post_parameters": post_params,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "document_type": "SI",
        }
        
    except Exception as e:
        print(f"⚠️ Błąd przy wyciąganiu parametrów z onclick: {e}")
        return None


def capture_request_from_onclick(driver, link_element, clear_before: bool = False) -> Optional[dict]:
    """
    Przechwytuje POST request wywoływany przez onclick PRZED jego faktycznym wysłaniem.
    Używa wstrzykniętego JavaScript do przechwycenia requestu i anulowania go.
    Zwraca dict z URL i parametrami POST.
    """
    global _captured_requests
    
    try:
        link_id = link_element.get_attribute("id")
        if not link_id:
            return None

        before_count = len(get_captured_requests(driver))

        if clear_before:
            driver.execute_script("window._capturedRequests = [];")
            before_count = 0

        driver.execute_script("arguments[0].click();", link_element)
        
        # Czekamy krótko na przechwycenie
        time.sleep(2)

        captured_list = get_captured_requests(driver)
        new_requests = captured_list[before_count:]
        
        for req in new_requests:
            if (req.get("method") == "POST" and 
                "handelsregister.de" in req.get("url", "") and 
                link_id in req.get("post_data", "")):

                _captured_requests.append(req)
                return req

        for req in captured_list:
            if (req.get("method") == "POST" and 
                "handelsregister.de" in req.get("url", "") and 
                link_id in req.get("post_data", "")):

                if req not in _captured_requests:
                    _captured_requests.append(req)
                    return req
        
        return None
        
    except Exception as e:
        print(f"⚠️ Błąd przy przechwytywaniu requestu: {e}")
        return None


def reconstruct_download_url(driver, link_element, onclick: str) -> tuple[Optional[str], Optional[dict], Optional[dict]]:
    """
    Wyciąga parametry POST z onclick BEZ wykonywania kliknięcia i BEZ pobierania pliku.
    TYLKO parsuje JavaScript z onclick - NIE KLIKA!
    Zwraca tuple: (base_url, post_params_dict, captured_request_dict)
    """
    try:
        current_url = driver.current_url.split("#")[0]
        link_id = link_element.get_attribute("id") or ""
        
        # Wyciągamy parametry z onclick BEZ klikania
        captured_request = extract_params_from_onclick(onclick, link_id, current_url)
        
        if captured_request:
            url = captured_request.get("url")
            post_params = captured_request.get("post_parameters", {})
            return url, post_params, captured_request
        
        return None, None, None
        
    except Exception as e:
        print(f"⚠️ Błąd przy wyciąganiu parametrów z onclick: {e}")
        return None, None, None


def extract_link_info(link_element, driver=None) -> Dict[str, Any]:
    """
    Wyciąga szczegółowe informacje o linku, w tym rzeczywisty URL dla linków z href="#".
    Dla PrimeFaces linków z onclick, próbuje wyciągnąć parametry z JavaScript.
    Jeśli podano driver, próbuje przechwycić rzeczywisty URL do pobrania.
    """
    try:
        href = link_element.get_attribute("href") or "#"
        text = link_element.text.strip()
        title = link_element.get_attribute("title") or ""
        onclick = link_element.get_attribute("onclick") or ""
        id_attr = link_element.get_attribute("id") or ""
        
        # Sprawdzamy różne atrybuty, które mogą zawierać URL
        data_url = link_element.get_attribute("data-url") or link_element.get_attribute("data-href")
        formaction = link_element.get_attribute("formaction")
        
        link_info = {
            "href": href,
            "text": text,
            "title": title,
            "id": id_attr,
            "onclick": onclick[:500] if onclick else "",  # Pierwsze 500 znaków onclick
            "data_url": data_url,
            "formaction": formaction,
        }
        
        # Jeśli href to "#", próbujemy wyciągnąć więcej informacji
        if href == "#" or href.startswith("javascript:") or (href and "#" in href and href.endswith("#")):
            # Dla PrimeFaces - wyciągamy ID elementu i parametry z onclick
            if id_attr:
                link_info["element_id"] = id_attr
                
            # Próbujemy wyciągnąć parametry z onclick (dla PrimeFaces)
            if "PrimeFaces" in onclick:
                property_match = re.search(r"'property':\s*'([^']+)'", onclick)
                if property_match:
                    link_info["property"] = property_match.group(1)

                form_match = re.search(r"submit\(['\"]([^'\"]+)['\"]\)", onclick)
                if form_match:
                    link_info["form_name"] = form_match.group(1)

        actual_url = href
        if data_url:
            actual_url = data_url
        elif formaction:
            actual_url = formaction
        elif href != "#" and not href.startswith("javascript:") and not (href.endswith("#") and "#" in href):
            actual_url = href

        if driver and "PrimeFaces" in onclick and "Global.Dokumentart.SI" in onclick:
            try:
                base_url, post_params, captured_request = reconstruct_download_url(driver, link_element, onclick)
                if base_url and post_params:
                    link_info["request_url"] = base_url
                    actual_url = base_url
                    
                    # Szczegółowe informacje o POST request
                    link_info["request"] = {
                        "method": "POST",
                        "url": base_url,
                        "content_type": "application/x-www-form-urlencoded",
                        "parameters": post_params,
                    }
                    
                    # Jeśli przechwyciliśmy rzeczywisty request, dodajemy szczegóły z pełnymi danymi
                    if captured_request:
                        link_info["captured_request"] = {
                            "url": captured_request.get("url"),
                            "method": captured_request.get("method"),
                            "post_data": captured_request.get("post_data"),  # Surowy string POST data
                            "post_parameters": captured_request.get("post_parameters"),  # Parsowane parametry
                            "timestamp": captured_request.get("timestamp"),
                            "document_type": captured_request.get("document_type", "SI"),
                        }
                    
                    # Dodatkowo: URL z parametrami jako GET (dla informacji, choć faktycznie to POST)
                    get_params = "&".join([f"{k}={v}" for k, v in post_params.items()])
                    link_info["request_url_with_params"] = f"{base_url}?{get_params}"
            except Exception as e:
                print(f"⚠️ Błąd przy przechwytywaniu requestu dla linku {id_attr}: {e}")
        
        link_info["actual_url"] = actual_url
        
        return link_info
        
    except Exception as e:
        return {
            "href": "#",
            "text": "",
            "title": "",
            "error": str(e),
            "actual_url": "#"
        }


def run_full_flow(target_url: str, download_dir: str = "") -> None:
    driver = None
    try:
        driver = build_driver()
        wait = WebDriverWait(driver, 10)
        driver.get(target_url)

        inject_request_interceptor(driver)

        print("NORMAL SUCHE")
        normale_suche = wait.until(
            EC.element_to_be_clickable((By.ID, "naviForm:normaleSucheLink"))
        )
        normale_suche.click()
        wait_for_loading_gone(driver)

        # 3. Wypełnianie formularza (INPUT DATA)
        print(f"SEARCH PAGE")

        # HRB #
        register_label = wait.until(EC.element_to_be_clickable((By.ID, "form:registerArt_label")))
        register_label.click()
        time.sleep(1)
        hrb_option = wait.until(EC.element_to_be_clickable((By.XPATH, f"//li[contains(text(), '{SEARCH_TYPE}')]")))
        hrb_option.click()
        wait_for_loading_gone(driver)
        time.sleep(1)

        # NUMBER
        register_input = wait.until(EC.presence_of_element_located((By.ID, "form:registerNummer")))
        register_input.clear()
        register_input.send_keys(SEARCH_NUMBER)

        # ALL #
        register_label1 = wait.until(EC.element_to_be_clickable((By.ID, "form:registergericht_label")))
        register_label1.click()
        time.sleep(2)
        town_option = wait.until(EC.element_to_be_clickable((By.XPATH, f"//ul[@id='form:registergericht_items']//li[@data-label='{SEARCH_TOWN}']")))
        town_option.click()
        wait_for_loading_gone(driver)
        time.sleep(1)

        # Opcjonalnie: Ustawienie 100 wyników
        try:
            per_page_label = driver.find_element(By.ID, "form:ergebnisseProSeite_label")
            per_page_label.click()
            per_page_100 = wait.until(EC.element_to_be_clickable((By.XPATH, "//li[contains(@data-label, '100')]")))
            per_page_100.click()
            wait_for_loading_gone(driver)
        except Exception:
            print("⚠️ Nie udało się zmienić liczby wyników na 100, zostawiam domyślną.")

        # 4. Kliknięcie SZUKAJ
        suche_btn = driver.find_element(By.ID, "form:btnSuche")
        driver.execute_script("arguments[0].click();", suche_btn)

        wait.until(EC.presence_of_element_located((By.ID, "ergebnissForm:selectedSuchErgebnisFormTable_data")))
        wait_for_loading_gone(driver)

        rows = driver.find_elements(By.XPATH, "//tbody[@id='ergebnissForm:selectedSuchErgebnisFormTable_data']/tr")

        collected_links = []

        for row_index, row in enumerate(rows):
            try:
                si_links = row.find_elements(
                    By.XPATH, 
                    f".//a[contains(@onclick, 'Global.Dokumentart.SI')]"
                )
                
                row_data = {
                    "row_number": row_index,
                    "row_display": row_index + 1,
                    "si_links": []
                }

                for link in si_links:
                    try:
                        onclick = link.get_attribute("onclick") or ""
                        if "Global.Dokumentart.SI" not in onclick:
                            continue

                        # Sprawdzamy czy ID ma poprawny format z numerem wiersza
                        link_id = link.get_attribute("id") or ""
                        expected_id_pattern = f"ergebnissForm:selectedSuchErgebnisFormTable:{row_index}:"
                        if expected_id_pattern not in link_id:
                            print(f"⚠️ Wiersz {row_index}: Nieoczekiwany format ID: {link_id}")
                            continue
                        
                        # Przechwytujemy request
                        link_info = extract_link_info(link, driver)

                        if link_info.get("request") or link_info.get("captured_request"):
                            if not link_info.get("request") and link_info.get("captured_request"):
                                captured = link_info.get("captured_request")
                                link_info["request"] = {
                                    "method": captured.get("method", "POST"),
                                    "url": captured.get("url"),
                                    "content_type": "application/x-www-form-urlencoded",
                                    "parameters": captured.get("post_parameters", {}),
                                }
                            
                            row_data["si_links"].append(link_info)
                        else:
                            print(f"⚠️ Wiersz {row_index}: Nie udało się przechwycić requestu dla linku SI")
                            
                    except Exception as e:
                        print(f"⚠️ Błąd przy zbieraniu linku SI w wierszu {row_index}: {e}")
                        continue

                if row_data["si_links"]:
                    collected_links.append(row_data)

            except StaleElementReferenceException:
                print(f"⚠️ Rekord {row_index}: Element wygasł (DOM odświeżony).")
                continue
            except Exception as e:
                print(f"❌ Błąd przy rekordzie {row_index}: {e}")

        # Zapisujemy zebrane requesty z parametrami do JSON
        wynik = {
            "count": len(collected_links),
            "items": collected_links,
        }
        time.sleep(1)

        os.makedirs(os.path.dirname(OUTPUT_JSON) or ".", exist_ok=True)
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(wynik, f, indent=4, ensure_ascii=False)

        total_si_requests = sum(len(item.get("si_links", [])) for item in collected_links)
        print(f"Łącznie przechwycono {total_si_requests} requestów SI z parametrami POST")

    except Exception as e:
        print(f"❌ KRYTYCZNY BŁĄD SKRYPTU: {e}")
        # Zrzut ekranu do debugowania
        if driver:
            driver.save_screenshot("error_debug.png")
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    target_url = "https://www.handelsregister.de/"

    run_full_flow(target_url, download_dir="")