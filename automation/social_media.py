import os
import json
import time
import requests
import random
from enum import Enum
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from undetected_chromedriver import Chrome, ChromeOptions
from selenium_stealth import stealth
from utils.utils import log_info, log_error, log_success, log_warning
from utils import utils
from tiktok_captcha_solver import SeleniumSolver
from network import firebase_client

sad_captcha_api = "3b6d31ed7e2d30379012731c8ed1e65a"

# Enum dla platformy
class Platform(Enum):
    TIKTOK = "TikTok"

# Nowe enumy określające typ zgłoszenia

# Klasa zarządzająca kontami w Firestore
class AccountManager:
    """Zarządza bazą danych kont w Firestore."""

    def __init__(self):
        self.accounts_collection = "accounts_sm"

    def save_account(self, email, platform, password, accounts_followed, reported, sm_file):
        """Zapisuje konto w Firestore."""
        doc_id = email.split("@")[0]  # Nazwa dokumentu to lokalna część adresu e-mail
        data = {
            "email": email,
            "platform": platform.value,
            "password": password,
            "accounts_followed": accounts_followed,
            "reported": reported,
            "sm_file": sm_file
        }
        try:
            utils.db.collection(self.accounts_collection).document(doc_id).set(data)
            log_success(f"Konto {email} zapisane w Firestore wraz z plikiem: {sm_file}.")
        except Exception as e:
            log_error(f"Nie udało się zapisać konta {email}: {e}")

    def view_accounts(self, platform):
        """Wyświetla wszystkie konta dla danej platformy z Firestore."""
        try:
            accounts = utils.db.collection(self.accounts_collection).where("platform", "==", platform.value).stream()
            log_info(f"Konta dla platformy {platform.value}:")
            for account in accounts:
                data = account.to_dict()
                print(f"Email: {data['email']}, Platforma: {data['platform']}, Obserwowane konta: {len(data['accounts_followed'])}, Zgłoszone: {data['reported']}, Plik ciasteczek: {data['sm_file']}")
        except Exception as e:
            log_error(f"Nie udało się wczytać kont dla platformy {platform.value}: {e}")

# Klasa pobierająca dane z TikToka
class TikTok(AccountManager):
    """Pobiera dane kont TikTok z komentarzy pod filmem."""
    
    def setup_driver(self):
        options = ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--lang=pl-PL")
        # Usuwamy automatyzacyjne przełączniki, które mogą zdradzać działanie bota

        driver = Chrome(options=options, use_subprocess=True)

        driver.set_window_size(1920, 1080)

        # Używamy biblioteki selenium-stealth, aby ukryć niektóre ślady automatyzacji
        stealth(driver,
            languages=["pl-PL", "pl"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True
        )
        
        # Ukrycie właściwości wskazujących na automatyzację – wykonanie skryptu przy każdorazowym otwarciu nowego dokumentu
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                const proto = Object.getPrototypeOf(navigator);
                if (proto.hasOwnProperty('webdriver')) {
                    delete proto.webdriver;
                }
                const fakePluginsData = [
                    {
                        name: "PDF Viewer",
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        version: "",
                        mimeTypes: [
                            { type: "application/pdf", suffixes: "pdf", description: "Portable Document Format" },
                            { type: "text/pdf", suffixes: "pdf", description: "Portable Document Format" }
                        ]
                    },
                    {
                        name: "Chrome PDF Viewer",
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        version: "",
                        mimeTypes: [
                            { type: "application/pdf", suffixes: "pdf", description: "Portable Document Format" },
                            { type: "text/pdf", suffixes: "pdf", description: "Portable Document Format" }
                        ]
                    },
                    {
                        name: "Chromium PDF Viewer",
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        version: "",
                        mimeTypes: [
                            { type: "application/pdf", suffixes: "pdf", description: "Portable Document Format" },
                            { type: "text/pdf", suffixes: "pdf", description: "Portable Document Format" }
                        ]
                    },
                    {
                        name: "Microsoft Edge PDF Viewer",
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        version: "",
                        mimeTypes: [
                            { type: "application/pdf", suffixes: "pdf", description: "Portable Document Format" },
                            { type: "text/pdf", suffixes: "pdf", description: "Portable Document Format" }
                        ]
                    },
                    {
                        name: "WebKit built-in PDF",
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        version: "",
                        mimeTypes: [
                            { type: "application/pdf", suffixes: "pdf", description: "Portable Document Format" },
                            { type: "text/pdf", suffixes: "pdf", description: "Portable Document Format" }
                        ]
                    }
                ];
                const pluginArrayProto = Object.getPrototypeOf(navigator.plugins);
                const fakePluginArray = Object.create(pluginArrayProto);
                Object.defineProperty(fakePluginArray, 'item', { 
                    value: function(index) { return this[index]; },
                    writable: false,
                    configurable: false,
                    enumerable: false
                });
                Object.defineProperty(fakePluginArray, 'namedItem', { 
                    value: function(name) {
                        for (let i = 0; i < this.length; i++) {
                            if (this[i].name === name) return this[i];
                        }
                        return null;
                    },
                    writable: false,
                    configurable: false,
                    enumerable: false
                });
                fakePluginsData.forEach((pluginData, index) => {
                    let fakePlugin;
                    if (navigator.plugins.length > 0) {
                        fakePlugin = Object.create(Object.getPrototypeOf(navigator.plugins.item(0)));
                    } else {
                        fakePlugin = {};
                    }
                    Object.defineProperty(fakePlugin, 'name', { value: pluginData.name, writable: false, configurable: false, enumerable: false });
                    Object.defineProperty(fakePlugin, 'description', { value: pluginData.description, writable: false, configurable: false, enumerable: false });
                    Object.defineProperty(fakePlugin, 'filename', { value: pluginData.filename, writable: false, configurable: false, enumerable: false });
                    Object.defineProperty(fakePlugin, 'version', { value: pluginData.version, writable: false, configurable: false, enumerable: false });
                    pluginData.mimeTypes.forEach((mt, i) => {
                        Object.defineProperty(fakePlugin, i, { value: mt, writable: false, configurable: false, enumerable: true });
                    });
                    Object.defineProperty(fakePlugin, 'length', { value: pluginData.mimeTypes.length, writable: false, configurable: false, enumerable: false });
                    Object.defineProperty(fakePluginArray, index, { value: fakePlugin, writable: false, configurable: false, enumerable: true });
                });
                Object.defineProperty(fakePluginArray, 'length', { value: fakePluginsData.length, writable: false, configurable: false, enumerable: false });
                Object.defineProperty(navigator, 'plugins', {
                    get: function() { return fakePluginArray; },
                    configurable: false,
                    enumerable: true
                });
                Object.defineProperty(navigator, 'languages', { get: () => ['pl-PL', 'pl'] });
                Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            """
        })

        self.mouse_position = (random.randint(50, 150), random.randint(50, 150))
        return driver

    @staticmethod
    def load_cookies_from_firestore(email):
        """Wczytuje ciasteczka z Firestore Storage na podstawie informacji w dokumencie Firestore."""
        try:
            accounts_collection = "accounts_sm"
            doc_id = email.split("@")[0]
            doc = utils.db.collection(accounts_collection).document(doc_id).get()

            if not doc.exists:
                log_error(f"Dokument konta dla {email} nie istnieje w Firestore.")
                return []

            data = doc.to_dict()
            sm_file = data.get("sm_file")
            if not sm_file:
                log_error(f"Brak pliku ciasteczek dla konta {email}.")
                return []

            blob = utils.storage_bucket.blob(sm_file)
            if not blob.exists():
                log_error(f"Nie znaleziono pliku ciasteczek w Firebase Storage dla ścieżki: {sm_file}")
                return []

            file_url = f"https://firebasestorage.googleapis.com/v0/b/{utils.storage_bucket.name}/o/{sm_file.replace('/', '%2F')}?alt=media"
            log_info(f"Generowany link do pliku ciasteczek: {file_url}")

            response = requests.get(file_url)
            response.raise_for_status()
            cookies = response.json()

            log_success(f"Ciasteczka dla konta {email} wczytane z Firestore Storage.")
            return cookies if isinstance(cookies, list) else cookies.get("cookies", [])
        except Exception as e:
            log_error(f"Nie udało się wczytać ciasteczek dla {email}: {e}")
            return []

    @staticmethod
    def apply_cookies(driver, cookies):
        """
        Dodaje ciasteczka do przeglądarki Selenium.
        Sprawdza wymagane pola i obsługuje błędy.
        """
        for cookie in cookies:
            try:
                if 'name' not in cookie or 'value' not in cookie:
                    log_warning(f"Pominięto ciasteczko: brak wymaganych pól 'name' lub 'value'. Ciasteczko: {cookie}")
                    continue
                if 'sameSite' in cookie and cookie['sameSite'].lower() not in ['lax', 'strict', 'none']:
                    del cookie['sameSite']
                driver.add_cookie(cookie)
            except Exception as e:
                log_warning(f"Nie udało się dodać ciasteczka {cookie.get('name', 'unknown')}: {e}")

        log_success("Plik Session Manager został załadowany do przeglądarki")

    @staticmethod
    def save_profile_picture(username, img_data):
        """Zapisuje zdjęcie profilowe do Firestore Storage."""
        try:
            file_name = f"pfps/{username}.jpg"
            blob = utils.storage_bucket.blob(file_name)
            blob.upload_from_string(img_data, content_type="image/jpeg")
            log_success(f"Zdjęcie profilowe {username} zapisane w Firestore Storage.")
            return blob.public_url
        except Exception as e:
            log_error(f"Nie udało się zapisać zdjęcia profilowego {username}: {e}")
            return None

    def get_random_tiktok_account(self):
        """Losowo wybiera konto TikTok z Firestore."""
        try:
            accounts = utils.db.collection(self.accounts_collection).where("platform", "==", Platform.TIKTOK.value).stream()
            accounts_list = [account.to_dict() for account in accounts]

            if not accounts_list:
                log_warning("Brak dostępnych kont TikTok w bazie danych.")
                return None

            selected_account = random.choice(accounts_list)
            log_info(f"Wylosowano konto: {selected_account['email']}")
            return selected_account
        except Exception as e:
            log_error(f"Nie udało się wylosować konta TikTok: {e}")
            return None

    async def copy_accounts(self, task_id, user_id, url):
        """Pobiera komentarze, nazwy użytkowników i zdjęcia profilowe z podanego URL."""
        try:
            account = self.get_random_tiktok_account()
            if not account:
                log_error("Nie udało się wybrać konta do kopiowania.")
                return

            email = account['email']
            cookies = self.load_cookies_from_firestore(email)
            if not cookies:
                log_error(f"Brak ciasteczek dla konta {email}.")
                return
            
            chrome_path = ChromeDriverManager().install()
            if "THIRD_PARTY_NOTICES.chromedriver" in chrome_path:
                chrome_path = chrome_path.replace("THIRD_PARTY_NOTICES.chromedriver", "chromedriver")
            service = Service(chrome_path)
            options = webdriver.ChromeOptions()
            options.add_argument("--incognito")
            options.add_argument("--disable-gpu")
            options.add_argument("--lang=pl-PL")
            driver = webdriver.Chrome(service=service, options=options)

            sadcaptcha = SeleniumSolver(
                driver,
                sad_captcha_api,
                mouse_step_size=1,
                mouse_step_delay_ms=10
            )

            driver.get("https://www.tiktok.com/")
            wait = WebDriverWait(driver, 20)
            shadow_host = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tiktok-cookie-banner"))
            )
            shadow_root = driver.execute_script("return arguments[0].shadowRoot", shadow_host)
            WebDriverWait(shadow_root, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div > div.button-wrapper > button:nth-child(2)"))
            ).click()

            driver.delete_all_cookies()
            self.apply_cookies(driver, cookies)
            driver.refresh()
            driver.get(url)
            time.sleep(5)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)
            sadcaptcha.solve_captcha_if_present()
            time.sleep(10)

            # Pobieranie komentarzy
            comments = driver.find_elements(By.CLASS_NAME, "css-13wx63w-DivCommentObjectWrapper")
            for comment in comments:
                try:
                    username_elem = comment.find_element(By.CSS_SELECTOR, "p.TUXText.TUXText--tiktok-sans.TUXText--weight-medium[font-size='14']")
                    username = username_elem.text

                    img_elem = comment.find_element(By.TAG_NAME, "img")
                    img_url = img_elem.get_attribute("src")

                    img_data = requests.get(img_url).content
                    self.save_profile_picture(username, img_data)
                except Exception as e:
                    log_warning(f"Problem z pobraniem danych komentarza: {e}")

            driver.quit()
        except Exception as e:
            log_error(f"Błąd podczas pobierania danych: {e}")
            
    async def mass_report(self, task_id, user_id, url, report_count, main_report_choice, sub_report_choice=None):
        """Pobiera komentarze, nazwy użytkowników i zdjęcia profilowe z podanego URL,
        a następnie wykonuje operację zgłoszenia (report) – report_count razy.
        
        Parametry:
            task_id: str - identyfikator zadania przekazywany przez TaskMonitor
            user_id: str - identyfikator użytkownika wykonującego zgłoszenie
            url: str - adres URL do zgłoszenia
            report_count: int lub str - liczba zgłoszeń do wykonania (konwertowana na int)
            main_report_choice: ReportTypeMain - wybrana wartość głównego enuma
            sub_report_choice: (opcjonalnie) ReportTypeSub* - wybrana wartość podenuma, jeśli dotyczy
        """
        try:
            # Konwersja liczby zgłoszeń na int
            report_count_int = int(report_count)
            
            for i in range(report_count_int):
                log_info(f"Reportowanie: {i+1}/{report_count_int} (zadanie: {task_id})")
                
                # Losowe wybranie konta
                account = self.get_random_tiktok_account()
                if not account:
                    log_error("Nie udało się wybrać konta do kopiowania.")
                    return
                email = account['email']
                doc_id = email.split('@')[0]
                cookies = self.load_cookies_from_firestore(email)
                if not cookies:
                    log_error(f"Brak ciasteczek dla konta {email}.")
                    return
                # Inicjalizacja drivera za pomocą metody setup_driver (zapisywana w self.driver)
                self.driver = self.setup_driver()
                driver = self.driver
                # Otwórz TikTok i zastosuj ciasteczka
                driver.get("https://www.tiktok.com/")
                wait = WebDriverWait(driver, 20)
                shadow_host = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "tiktok-cookie-banner"))
                )
                shadow_root = driver.execute_script("return arguments[0].shadowRoot", shadow_host)
                WebDriverWait(shadow_root, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "div > div.button-wrapper > button:nth-child(2)"))
                ).click()
                driver.delete_all_cookies()
                self.apply_cookies(driver, cookies)
                driver.refresh()
                driver.get(url)
                time.sleep(5)
                # Konfiguracja solvera captcha (przy użyciu self.driver)
                sadcaptcha = SeleniumSolver(
                    driver,
                    sad_captcha_api,
                    mouse_step_size=1,
                    mouse_step_delay_ms=10
                )
                sadcaptcha.solve_captcha_if_present()
                time.sleep(10)
                # Kliknięcie przycisku rozwijającego menu (more-menu)
                more_menu = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-e2e='more-menu-icon']"))
                )
                more_menu.click()
                time.sleep(1)
                
                # Kliknięcie opcji "Zgłoś"
                report_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.TUXMenuItem[data-e2e="more-menu-popover_report"]'))
                )
                report_button.click()
                time.sleep(1)
                
                # Wybór głównego powodu zgłoszenia na podstawie enuma
                reason_xpath = f"//label[@data-e2e='report-card-reason'][.//div[text()='{main_report_choice}']]"
                report_reason = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, reason_xpath))
                )
                report_reason.click()
                time.sleep(1)
                # Jeśli dostępny, wybór podpowodu zgłoszenia
                if sub_report_choice:
                    sub_reason_xpath = f"//label[@data-e2e='report-card-reason'][.//div[text()='{sub_report_choice}']]"
                    sub_report_reason = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, sub_reason_xpath))
                    )
                    sub_report_reason.click()
                    time.sleep(1)
                # Kliknięcie przycisku "Wyślij"
                send_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.css-wwwrxx-ButtonSubmit.ezqf9p619"))
                )
                send_button.click()
                time.sleep(1)
                # Kliknięcie przycisku "Zakończ" lub podobnego (jeśli występuje)
                complete_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.css-2y8gg6-ButtonFinish.ezqf9p623"))
                )
                complete_button.click()
                
                # Inkrementacja licznika zgłoszeń dla danego konta
                await firebase_client.increment_count(doc_id, "accounts_sm", "reported")
                
                # Odczekaj przed kolejnym zgłoszeniem
                #time.sleep(99)
                
                driver.quit()
                return True
        except Exception as e:
            driver.quit()
            log_error(f"Błąd podczas pobierania danych: {e}")
            return False