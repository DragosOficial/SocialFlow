import os
import random
import string
import time
import json
import calendar  # Do obliczania liczby dni w miesiącu
from network import firebase_client
from datetime import datetime, timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
from undetected_chromedriver import Chrome, ChromeOptions
from aiohttp import ClientSession
from enum import Enum
from utils import utils


# Enum for services
class Service(Enum):
    GOOGLE = "Google"
    # Możesz dodać więcej usług, jeśli zajdzie taka potrzeba


class Google:
    def __init__(self, platform="Google"):
        self.driver = None
        self.firebase = firebase_client
        self.platform = platform  # Zmienna platformy
        self.mouse_position = None  # Pozycja symulowanego kursora

    def setup_driver(self):
        options = ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--lang=pl-PL")
        # Usuwamy automatyzacyjne przełączniki, które mogą zdradzać działanie bota

        driver = Chrome(options=options, use_subprocess=True)

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
                // Usuń właściwość webdriver z prototypu navigator
                const proto = Object.getPrototypeOf(navigator);
                if (proto.hasOwnProperty('webdriver')) {
                    delete proto.webdriver;
                }
                
                // Definiujemy realistyczne dane pluginów z informacjami MIME
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
                
                // Pobieramy oryginalny prototyp PluginArray z navigator.plugins
                const pluginArrayProto = Object.getPrototypeOf(navigator.plugins);
                // Tworzymy fakePluginArray na podstawie oryginalnego prototypu
                const fakePluginArray = Object.create(pluginArrayProto);
                
                // Definiujemy metody item i namedItem, które są częścią interfejsu PluginArray
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
                
                // Dodajemy kolejne pluginy do fakePluginArray
                fakePluginsData.forEach((pluginData, index) => {
                    // Tworzymy obiekt pluginu – próbujemy wykorzystać oryginalny prototyp pojedynczego pluginu, jeśli jest dostępny
                    let fakePlugin;
                    if (navigator.plugins.length > 0) {
                        fakePlugin = Object.create(Object.getPrototypeOf(navigator.plugins.item(0)));
                    } else {
                        fakePlugin = {}; // Fallback, gdy navigator.plugins jest pusty
                    }
                    // Ustawiamy właściwości informacyjne jako nieenumerowalne
                    Object.defineProperty(fakePlugin, 'name', { value: pluginData.name, writable: false, configurable: false, enumerable: false });
                    Object.defineProperty(fakePlugin, 'description', { value: pluginData.description, writable: false, configurable: false, enumerable: false });
                    Object.defineProperty(fakePlugin, 'filename', { value: pluginData.filename, writable: false, configurable: false, enumerable: false });
                    Object.defineProperty(fakePlugin, 'version', { value: pluginData.version, writable: false, configurable: false, enumerable: false });
                    // Dodajemy MIME types jako właściwości numeryczne (enumerowalne)
                    pluginData.mimeTypes.forEach((mt, i) => {
                        Object.defineProperty(fakePlugin, i, { value: mt, writable: false, configurable: false, enumerable: true });
                    });
                    // Ustawiamy długość pojedynczego pluginu (ilość MIME types) jako właściwość nieenumerowalną
                    Object.defineProperty(fakePlugin, 'length', { value: pluginData.mimeTypes.length, writable: false, configurable: false, enumerable: false });
                    // Dodajemy plugin do fakePluginArray jako właściwość numeryczną
                    Object.defineProperty(fakePluginArray, index, { value: fakePlugin, writable: false, configurable: false, enumerable: true });
                });
                // Ustawiamy długość fakePluginArray jako właściwość nieenumerowalną
                Object.defineProperty(fakePluginArray, 'length', { value: fakePluginsData.length, writable: false, configurable: false, enumerable: false });
                
                // Nadpisujemy właściwość navigator.plugins, aby zwracała nasz fakePluginArray
                Object.defineProperty(navigator, 'plugins', {
                    get: function() { return fakePluginArray; },
                    configurable: false,
                    enumerable: true
                });
                
                // Ustawienie preferowanych języków
                Object.defineProperty(navigator, 'languages', { get: () => ['pl-PL', 'pl'] });
                // Ukrycie platformy
                Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            """
        });

        # Inicjalizacja symulowanej pozycji kursora na losowej pozycji (np. w górnej części okna)
        self.mouse_position = (random.randint(50, 150), random.randint(50, 150))
        return driver

    def generate_random_string(self, length=10):
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def get_random_name(self, collection):
        docs = utils.db.collection(collection).stream()
        random_doc = random.choice([doc.to_dict() for doc in docs])
        return random_doc["original_name"] if "original_name" in random_doc else None

    def random_delay(self, min_delay=1.5, max_delay=3.5):
        time.sleep(random.uniform(min_delay, max_delay))

    def generate_birthdate(self):
        """
        Generuje losową datę urodzenia.
        Możesz zmienić zakres lat według potrzeb (np. aby użytkownik miał co najmniej 18 lat).
        """
        year = random.randint(1970, 2002)  # przykładowy zakres lat
        month = random.randint(1, 12)
        day = random.randint(1, calendar.monthrange(year, month)[1])
        return day, month, year

    def fill_birthdate_and_gender(self):
        """
        Wypełnia pola daty urodzenia (dzień, miesiąc, rok) oraz wybiera płeć męską.
        Dodatkowo zapisuje datę urodzenia oraz płeć w atrybutach instancji.
        """
        day, month, year = self.generate_birthdate()

        # Zapisujemy datę urodzenia w formacie DD-MM-YYYY
        self.birth_date = f"{day:02d}-{month:02d}-{year}"
        # Ustawiamy płeć na "Mężczyzna"
        self.gender = "Mężczyzna"

        # Wypełnienie pola dnia
        day_field = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "day"))
        )
        day_field.clear()
        self.human_typing(day_field, str(day))
        self.random_delay()

        # Wybór miesiąca z listy – wykorzystujemy obiekt Select
        month_select_element = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "month"))
        )
        month_select = Select(month_select_element)
        month_select.select_by_value(str(month))  # Wartość odpowiadająca miesiącowi (1-12)
        self.random_delay()

        # Wypełnienie pola roku
        year_field = self.driver.find_element(By.ID, "year")
        year_field.clear()
        self.human_typing(year_field, str(year))
        self.random_delay()

        # Wybór płci – zakładamy, że opcja męska ma wartość "1"
        gender_select_element = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "gender"))
        )
        gender_select = Select(gender_select_element)
        gender_select.select_by_value("1")  # "1" – mężczyzna
        self.random_delay()

    def normalize_name(self, name):
        """
        Zamienia polskie znaki diakrytyczne na odpowiedniki łacińskie
        oraz zmienia tekst na małe litery.
        """
        mapping = {
            ord('ą'): 'a', ord('ć'): 'c', ord('ę'): 'e',
            ord('ł'): 'l', ord('ń'): 'n', ord('ó'): 'o',
            ord('ś'): 's', ord('ź'): 'z', ord('ż'): 'z',
            ord('Ą'): 'a', ord('Ć'): 'c', ord('Ę'): 'e',
            ord('Ł'): 'l', ord('Ń'): 'n', ord('Ó'): 'o',
            ord('Ś'): 's', ord('Ź'): 'z', ord('Ż'): 'z'
        }
        return name.translate(mapping).lower()

    def human_typing(self, element, text):
        """
        Symuluje powolne, ludzkie pisanie – wpisuje znak po znaku z losowym opóźnieniem.
        """
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.1, 0.25))

    def human_like_mouse_move(self, target_x, target_y):
        """
        Przesuwa kursor myszy w sposób przypominający ruchy ludzkie.
        Obliczamy małe kroki od bieżącej pozycji do celu.
        """
        if self.mouse_position is None:
            self.mouse_position = (target_x, target_y)
            return
        start_x, start_y = self.mouse_position
        dx = target_x - start_x
        dy = target_y - start_y
        steps = random.randint(15, 25)
        for step in range(1, steps + 1):
            # Obliczamy kolejne pośrednie współrzędne z lekkim losowym zaburzeniem
            intermediate_x = start_x + dx * step / steps + random.uniform(-2, 2)
            intermediate_y = start_y + dy * step / steps + random.uniform(-2, 2)
            offset_x = intermediate_x - self.mouse_position[0]
            offset_y = intermediate_y - self.mouse_position[1]
            ActionChains(self.driver).move_by_offset(offset_x, offset_y).perform()
            self.mouse_position = (intermediate_x, intermediate_y)
            time.sleep(random.uniform(0.01, 0.03))

    def move_mouse_to_element(self, element):
        """
        Przesuwa kursor myszy do środka wskazanego elementu.
        """
        rect = element.rect
        target_x = rect['x'] + rect['width'] / 2
        target_y = rect['y'] + rect['height'] / 2
        self.human_like_mouse_move(target_x, target_y)

    def human_click(self, element):
        """
        Realistyczne klikanie: najpierw przesuwa kursor myszy do elementu, czeka losowy czas,
        a następnie wykonuje kliknięcie.
        """
        self.move_mouse_to_element(element)
        time.sleep(random.uniform(0.2, 0.5))
        # Dodatkowe drobne "drganie" kursora przed kliknięciem
        ActionChains(self.driver).move_by_offset(random.randint(-2, 2), random.randint(-2, 2)).perform()
        time.sleep(random.uniform(0.1, 0.2))
        ActionChains(self.driver).move_to_element(element).click().perform()
        time.sleep(random.uniform(0.2, 0.5))

    def generate_account(self):
        self.driver = self.setup_driver()
        first_name = self.get_random_name("names_database")
        last_name = self.get_random_name("last_names_database")

        # Zapisujemy imię i nazwisko w atrybutach instancji
        self.first_name = first_name
        self.last_name = last_name

        # Normalizacja imienia i nazwiska – zamiana polskich znaków na łacińskie oraz zmiana na małe litery
        first_name_norm = self.normalize_name(first_name)
        last_name_norm = self.normalize_name(last_name)

        # Łączymy imię i nazwisko w jeden ciąg
        combined = first_name_norm + last_name_norm

        if len(combined) < 2:
            username_core = combined
        else:
            # Wybieramy dwa unikalne indeksy, aby wstawić symbole (kropki)
            positions = random.sample(range(1, len(combined)), 2)
            positions.sort()
            p1, p2 = positions
            sym1 = sym2 = '.'
            username_core = combined[:p1] + sym1 + combined[p1:p2] + sym2 + combined[p2:]
        # Generujemy losowe dwie cyfry
        digits = random.randint(10, 99)
        username = f"{username_core}{digits}"
        email = f"{username}@gmail.com"
        password = self.generate_random_string(12)

        self.driver.get("https://accounts.google.com/signup/v2/webcreateaccount?service=youtube")
        self.random_delay()

        # Kliknięcie przycisku "Utwórz konto"
        utworz_konto_button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Utwórz konto')]"))
        )
        self.human_click(utworz_konto_button)
        self.random_delay()

        # Kliknięcie opcji "Do użytku osobistego"
        osobiste_option = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//li[.//span[text()='Do użytku osobistego']]"))
        )
        self.human_click(osobiste_option)
        self.random_delay()

        # Wpisywanie imienia i nazwiska
        first_name_field = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "firstName"))
        )
        self.move_mouse_to_element(first_name_field)
        self.human_typing(first_name_field, first_name)
        self.random_delay()

        last_name_field = self.driver.find_element(By.ID, "lastName")
        self.move_mouse_to_element(last_name_field)
        self.human_typing(last_name_field, last_name)
        self.random_delay()

        next_button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'VfPpkd-LgbsSe') and contains(., 'Dalej')]"))
        )
        self.human_click(next_button)
        self.random_delay()

        # Wypełnienie daty urodzenia i wyboru płci
        self.fill_birthdate_and_gender()
        self.random_delay()
        next_button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'VfPpkd-LgbsSe') and contains(., 'Dalej')]"))
        )
        self.human_click(next_button)
        self.random_delay()

        # Po wpisaniu daty urodzenia:
        # 1. Kliknij pierwszą opcję "Utwórz adres Gmail"
        first_option = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@jsname='wQNmvb']//div[@id='selectionc1' and contains(., 'Utwórz adres Gmail')]"))
        )
        self.human_click(first_option)
        self.random_delay()

        # 2. Kliknij przycisk "Dalej"
        next_button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'VfPpkd-LgbsSe') and contains(., 'Dalej')]"))
        )
        self.human_click(next_button)
        self.random_delay()

        # 3. Kliknij drugą opcję "Utwórz własny adres Gmail"
        second_option = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@jsname='wQNmvb']//div[@id='selectionc6' and contains(., 'Utwórz własny adres Gmail')]"))
        )
        self.human_click(second_option)
        self.random_delay()

        username_field = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.NAME, "Username"))
        )
        self.move_mouse_to_element(username_field)
        self.human_typing(username_field, username)
        self.random_delay()

        next_button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'VfPpkd-LgbsSe') and contains(., 'Dalej')]"))
        )
        self.human_click(next_button)
        self.random_delay()

        # Wpisywanie hasła
        passwd_field = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "Passwd"))
        )
        self.move_mouse_to_element(passwd_field)
        self.human_typing(passwd_field, password)
        self.random_delay()

        passwd_again_field = self.driver.find_element(By.NAME, "PasswdAgain")
        self.move_mouse_to_element(passwd_again_field)
        self.human_typing(passwd_again_field, password)
        self.random_delay()

        next_button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'VfPpkd-LgbsSe') and contains(., 'Dalej')]"))
        )
        self.human_click(next_button)

        # Zapis danych konta do Firebase
        self.save_to_firebase(email, password)


    async def save_to_firebase(self, email, password):
        session_data = {
            "email": email,
            "password": password,
            "user_agent": self.driver.execute_script("return navigator.userAgent"),
            "cookies": self.driver.get_cookies() #
        }

        # Tworzymy sub_id na podstawie e-maila
        cut_email = email.split("@")[0]

        # Przygotowanie pliku JSON z cookies do wysłania do Firebase Storage
        cookies_file_path = f"Session Manager/{self.platform}/{cut_email}.json"  # Używamy platformy w ścieżce
        cookies_json = json.dumps(session_data["cookies"], default=str)

        # Zapisz plik cookies w Firebase Storage
        blob = utils.storage_bucket.blob(cookies_file_path)
        blob.upload_from_string(cookies_json, content_type="application/json")

        # Przygotowujemy dane do zapisania w Firestore (link do pliku w Firebase Storage)
        data = {
            "email": email,
            "password": password,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "birth_date": self.birth_date,
            "gender": self.gender,
            "user_agent": session_data["user_agent"],
            "cookies": f"{cookies_file_path}"  # Link do pliku
        }

        # Wysyłamy dane do Firestore
        async with ClientSession() as session:
            await firebase_client.save_user_data(session, cut_email, data, "mail_database")

        print(f"Konto zapisane w Firebase: {email}")

    def close(self):
        if self.driver:
            self.driver.quit()