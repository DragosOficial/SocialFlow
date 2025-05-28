import os
import sqlite3
import random
import string
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from cryptography.fernet import Fernet
from webdriver_manager.chrome import ChromeDriverManager
from utils.utils import log_success, log_error, log_info, log_warning
import time
from datetime import datetime, timedelta
import re

# Klucz szyfrowania
fernet_key = "r-tyOCIy_Y1CHVqcEqL5qZPxqOcbYQ_2qjI5Gc0B8YE="
cipher = Fernet(fernet_key.encode())

class EmailBankBase:
    def __init__(self, db_name):
        self.db_name = db_name
        self.username_counter = 1
        self.letter_index = 0  # Dodane do obsługi liter
        self.setup_database()
        log_info(f"Inicjalizacja {self.__class__.__name__} zakończona.")

    def setup_database(self):
        """Inicjalizuje bazę danych i tabelę do przechowywania kont e-mail."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL,
                    password TEXT NOT NULL
                )
            """)
        log_success(f"Baza danych {self.db_name} skonfigurowana.")

    def generate_username(self, prefix="SocialFlow"):
        """Generuje unikalny login e-mail."""
        letters = "abcdefghijklmnopqrstuvwxyz"
        username = f"{prefix}{self.username_counter:03}{letters[self.letter_index]}"
        self.letter_index = (self.letter_index + 1) % 26
        if self.letter_index == 0:  # Zwiększamy licznik po przejściu przez wszystkie litery
            self.username_counter += 1
        log_info(f"Wygenerowano nową nazwę użytkownika: {username}")
        return username

    def generate_password(self, length=12):
        """Generuje losowe hasło o zadanej długości."""
        letters = string.ascii_letters
        digits = string.digits
        punctuation = string.punctuation

        num_letters = length - 2
        num_digits = 1
        num_punctuation = 1

        password_letters = [random.choice(letters) for _ in range(num_letters)]
        password_digits = [random.choice(digits) for _ in range(num_digits)]
        password_punctuation = [random.choice(punctuation) for _ in range(num_punctuation)]

        password = password_letters + password_digits + password_punctuation
        random.shuffle(password)

        final_password = ''.join(password)
        log_info(f"Wygenerowano nowe hasło: {final_password}")
        return final_password

    def generate_birthdate(self):
        """Generuje losową datę urodzenia."""
        today = time.localtime()
        earliest_year = today.tm_year - 19
        latest_year = today.tm_year - 23
        year = random.randint(latest_year, earliest_year)
        month_number = random.randint(1, 12)
        
        month_names = [
            "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
            "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"
        ]
        month_name = month_names[month_number - 1]

        if month_number == 2:
            day = random.randint(1, 29)
        elif month_number in [4, 6, 9, 11]:
            day = random.randint(1, 30)
        else:
            day = random.randint(1, 31)

        return f"{day}/{month_name}/{year}"

    def save_account(self, email, password):
        """Zapisuje zaszyfrowane konto w bazie danych."""
        encrypted_password = cipher.encrypt(password.encode())
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO accounts (email, password) VALUES (?, ?)", (email, encrypted_password))
            conn.commit()
        log_success(f"Konto {email} zostało zapisane w bazie danych.")

    def delete_account(self, email):
        """Usuwa konto z bazy danych."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE email = ?", (email,))
            conn.commit()
        log_success(f"Konto {email} zostało usunięte z bazy danych.")

    def view_accounts(self):
        """Wyświetla wszystkie konta zapisane w bazie danych."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email, password FROM accounts")
            accounts = cursor.fetchall()
            log_info("Wyświetlanie zapisanych kont.")
            for email, encrypted_password in accounts:
                decrypted_password = cipher.decrypt(encrypted_password).decode()
                print(f"Email: {email}, Hasło: {decrypted_password}")

    def export_to_file(self, filename="accounts.txt"):
        """Eksportuje konta do zaszyfrowanego pliku."""
        try:
            with open(filename, "wb") as f:
                with sqlite3.connect(self.db_name) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT email, password FROM accounts")
                    accounts = cursor.fetchall()
                    data = "\n".join([f"{email}:{cipher.decrypt(pw).decode()}" for email, pw in accounts])
                    f.write(cipher.encrypt(data.encode()))
            log_success(f"Konta zostały zapisane do zaszyfrowanego pliku {filename}.")
        except Exception as e:
            log_error(f"Nie udało się zapisać kont do pliku: {e}")

    def load_from_file(self, filename="accounts.txt"):
        """Wczytuje zaszyfrowane konta z pliku."""
        if os.path.exists(filename):
            try:
                with open(filename, "rb") as f:
                    encrypted_data = f.read()
                    data = cipher.decrypt(encrypted_data).decode()
                    with sqlite3.connect(self.db_name) as conn:
                        cursor = conn.cursor()
                        for line in data.split("\n"):
                            email, password = line.split(":")
                            encrypted_password = cipher.encrypt(password.encode())
                            cursor.execute("INSERT OR IGNORE INTO accounts (email, password) VALUES (?, ?)", (email, encrypted_password))
                        conn.commit()
                log_success("Konta zostały wczytane z pliku.")
            except Exception as e:
                log_error(f"Nie udało się wczytać kont z pliku: {e}")
        else:
            log_warning(f"Plik {filename} nie istnieje.")

    def random_delay(self, min_delay=1.0, max_delay=2.0):
        """Wprowadza losowe opóźnienie."""
        time.sleep(random.uniform(min_delay, max_delay))

class GmailBank(EmailBankBase):
    def __init__(self):
        super().__init__(db_name="gmail_bank.db")

    def create_account(self):
        """Automatycznie tworzy nowe konto Gmail przez stronę YouTube, pomijając telefon..."""
        options = webdriver.ChromeOptions()
        driver_path = ChromeDriverManager().install()
        print(f"Zainstalowana wersja chromedrivera: {driver_path}")
        options.add_argument("--incognito")
        options.add_argument("--disable-gpu")
        options.add_argument("--lang=pl-PL")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        
        username = self.generate_username()
        email = f"{username}@gmail.com"
        password = self.generate_password()

        try:
            log_info("1")
            driver.get("https://accounts.google.com/signup/v2/webcreateaccount?service=youtube")
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[contains(@class, 'whsOnd')]"))
            )
            self.random_delay(2, 3)
            
            log_info("2")
            
            WebDriverWait(driver, 10).until( 
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'VfPpkd-LgbsSe') and contains(., 'Utwórz konto')]"))
            ).click()
            self.random_delay()
            
            log_info("3")
            
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//li[contains(@class, 'gNVsKb') and contains(., 'Do użytku osobistego')]"))
            ).click()
            self.random_delay()
            
            log_info("4")
            
            # Wprowadzanie imienia
            first_name_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "firstName"))
            )
            for char in "Social":
                first_name_field.send_keys(char)
                self.random_delay(0.1, 0.3)
            
            log_info("5")
            
            # Wprowadzanie nazwiska
            last_name_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "lastName"))
            )
            for char in "Flow":
                last_name_field.send_keys(char)
                self.random_delay(0.1, 0.3)
            
            log_info("6")
            
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "collectNameNext"))
            ).click()
            self.random_delay()

            # Wprowadzenie daty urodzenia
            birthdate = self.generate_birthdate()
            day, month, year = birthdate.split('/')

            log_info("8")
            
            day_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[aria-label='Dzień']"))
            )
            for char in day:
                day_field.send_keys(char)
                self.random_delay(0.1, 0.2)
            
            log_info("9")
            
            month_select = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "month"))
            )
            Select(month_select).select_by_visible_text(month)
            self.random_delay()

            year_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[aria-label='Rok']"))
            )
            for char in year:
                year_field.send_keys(char)
                self.random_delay(0.1, 0.2)
            
            log_info("11")
            
            gender_select = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "gender"))
            )
            Select(gender_select).select_by_visible_text("Mężczyzna")
            self.random_delay()
            
            log_info("12")
            
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'VfPpkd-LgbsSe') and contains(., 'Dalej')]"))
            ).click()
            self.random_delay()

            log_info("13")
            
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@class='dJVBl wIAG6d' and contains(text(), 'Utwórz adres Gmail')]"))
            ).click()
            self.random_delay()
            
            log_info("14")
            
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'VfPpkd-LgbsSe') and contains(., 'Dalej')]"))
            ).click()
            self.random_delay()
            
            log_info("15")
            
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@class='dJVBl wIAG6d' and contains(text(), 'Utwórz własny adres Gmail')]"))
            ).click()
            self.random_delay()

            # Wprowadzanie nazwy użytkownika
            log_info("16")
            
            username_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@aria-label='Utwórz adres Gmail']"))
            )
            for char in username:
                username_field.send_keys(char)
                self.random_delay(0.1, 0.3)
            
            log_info("17")
            
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'VfPpkd-LgbsSe') and contains(., 'Dalej')]"))
            ).click()
            self.random_delay()

            # Wprowadzenie hasła
            log_info("18")
            
            password_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@aria-label='Hasło']"))
            )
            for char in password:
                password_field.send_keys(char)
                self.random_delay(0.1, 0.3)
            
            # Potwierdzenie hasła
            log_info("19")
            
            confirm_password_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@aria-label='Potwierdź']"))
            )
            for char in password:
                confirm_password_field.send_keys(char)
                self.random_delay(0.1, 0.3)
            
            log_info("20")
            
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'VfPpkd-LgbsSe') and contains(., 'Dalej')]"))
            ).click()
            self.random_delay()
            
            log_info("21")
            
            time.sleep(9999)
            self.save_account(email, password)
            log_success(f"Konto Gmail zostało utworzone i zapisane jako {email}.")

        except Exception as e:
            log_error(f"Nie udało się utworzyć konta Gmail: {e}")
        finally:
            driver.quit()

class OnetBank(EmailBankBase):

    def __init__(self):
        super().__init__(db_name="onet_bank.db")

    def create_account(self):
        """Automatycznie tworzy nowe konto Onet przez stronę YouTube, pomijając telefon."""
        options = webdriver.ChromeOptions()
        driver_path = ChromeDriverManager().install()
        print(f"Zainstalowana wersja chromedrivera: {driver_path}")
        options.add_argument("--incognito")
        options.add_argument("--disable-gpu")
        options.add_argument("--lang=pl-PL")
        driver = webdriver.Chrome("C:\\Users\\dawfo\\.wdm\\drivers\\chromedriver\\win64\\130.0.6723.91\\chromedriver-win32\\chromedriver.exe", options=options)
        
        username = self.generate_username()
        email = f"{username}@op.pl"
        password = self.generate_password()
        birthdate = self.generate_birthdate()
        day, month, year = birthdate.split('/')

        try:
            log_info("1")
            driver.get("https://konto.onet.pl/register")

            time.sleep(9999)  # import time

            self.random_delay(2, 3)

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='go to advanced settings']"))
            ).click()
            self.random_delay()

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='reject and close']"))
            ).click()
            self.random_delay()

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "alias"))
            )
            for char in username:
                driver.find_element(By.ID, "alias").send_keys(char)
                self.random_delay(0.1, 0.3)
            log_info("2")

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.sc-d7d238e9-0.kKyUAv"))
            ).click()
            self.random_delay()

            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "newPassword"))
            )
            for char in password:
                driver.find_element(By.ID, "newPassword").send_keys(char)
                self.random_delay(0.1, 0.3)

            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "rePassword"))
            )
            for char in password:
                driver.find_element(By.ID, "rePassword").send_keys(char)
                self.random_delay(0.1, 0.3)

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.sc-d7d238e9-0.kKyUAv"))
            ).click()
            self.random_delay()

            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "phone"))
            ).send_keys("510669146")
            self.random_delay()

            WebDriverWait(driver, 999).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.sc-d7d238e9-0.kKyUAv"))
            ).click()
            self.random_delay()

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "M"))
            ).click()
            self.random_delay()

            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "name"))
            )
            for char in "Social Flow":
                driver.find_element(By.ID, "name").send_keys(char)
                self.random_delay(0.1, 0.3)

            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "birthDate.day"))
            ).send_keys(day)
            self.random_delay()

            month_select = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "birthDate.month"))
            )
            Select(month_select).select_by_visible_text(month)
            self.random_delay()

            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "birthDate.year"))
            ).send_keys(year)
            self.random_delay()

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.sc-d7d238e9-0.kKyUAv"))
            ).click()
            self.random_delay()

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "agreements.85"))
            ).click()
            self.random_delay()

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "agreements.6"))
            ).click()
            self.random_delay()

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "agreements.21"))
            ).click()
            self.random_delay()

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.sc-d7d238e9-0.kKyUAv"))
            ).click()
            self.random_delay()

            WebDriverWait(driver, 99999).until(
                EC.presence_of_element_located((By.CLASS_NAME, "sc-a17d6256-10 asXmN"))
            )
            self.save_account(email, password)
            log_success(f"Konto Onet zostało utworzone i zapisane jako {email}.")

        except Exception as e:
            log_error(f"Nie udało się utworzyć konta Onet: {e}")

        finally:
            driver.quit()

class ProtonBank(EmailBankBase):
    def __init__(self):
        super().__init__(db_name="proton_bank.db")

    def random_delay(self, min_seconds=0.5, max_seconds=2.0):
        time.sleep(random.uniform(min_seconds, max_seconds))

    def type_text_with_typo(self, element, text):
        for char in text:
            element.send_keys(char)
            self.random_delay(0.1, 0.3)
            if random.random() < 0.05:  # 5% szansy na pomyłkę
                element.send_keys("\b" + char)

    def observe_before_click(self, element, min_seconds=1, max_seconds=3):
        self.random_delay(min_seconds, max_seconds)
        element.click()

    def random_resize(self, driver):
        width = random.randint(800, 1200)
        height = random.randint(600, 900)
        driver.set_window_size(width, height)
        self.random_delay(0.5, 1.5)

    def random_scroll(self, driver):
        scroll_y = random.randint(50, 300)
        driver.execute_script(f"window.scrollTo(0, window.scrollY + {scroll_y});")
        self.random_delay(0.5, 1)

    def move_mouse_to_element(self, driver, element):
        action = ActionChains(driver)
        start_x = random.randint(0, driver.execute_script("return window.innerWidth") - 1)
        start_y = random.randint(0, driver.execute_script("return window.innerHeight") - 1)
        end_x, end_y = element.location['x'], element.location['y']
        
        x, y = start_x, start_y
        action.move_by_offset(x, y).perform()
        while abs(x - end_x) > 5 or abs(y - end_y) > 5:
            x += (end_x - x) * random.uniform(0.2, 0.3)
            y += (end_y - y) * random.uniform(0.2, 0.3)
            action.move_by_offset(x, y).perform()
            self.random_delay(0.05, 0.1)
        action.move_to_element(element).perform()

    def extract_verification_code(self, driver):

        # Czekaj, aż zawartość e-maila zostanie w pełni załadowana
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Your Proton verification code')]"))
        )

        # Pobierz treść e-maila
        email_body = driver.find_element(By.XPATH, "//body").text

        # Użyj wyrażenia regularnego, aby znaleźć sześciocyfrowy kod w treści e-maila
        code_match = re.search(r'\b\d{6}\b', email_body)
        if code_match:
            return code_match.group(0)  # Zwróć znaleziony kod
        else:
            return None

    def create_account(self):
        """Automatycznie tworzy nowe konto Proton."""
        options = webdriver.ChromeOptions()
        driver_path = "C:\\Users\\dawfo\\.wdm\\drivers\\chromedriver\\win64\\130.0.6723.91\\chromedriver-win32\\chromedriver.exe"
        print(f"Zainstalowana wersja chromedrivera: {driver_path}")
        options.add_argument("--incognito")
        options.add_argument("--disable-gpu")
        options.add_argument("--lang=pl-PL")
        driver = webdriver.Chrome(driver_path, options=options)
        
        target_email = "no-reply@verify.proton.me"
        username = self.generate_username()
        email = f"{username}@proton.me"
        password = self.generate_password()
        birthdate = self.generate_birthdate()
        day, month, year = birthdate.split('/')

        try:            
            driver.get("https://konto.onet.pl/signin?state=https%3A%2F%2Fpoczta.onet.pl%2F&client_id=poczta.onet.pl.front.onetapi.pl")
            log_info("Odwiedzana strona logowania Onet.")

            go_advaned_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='go to advanced settings']"))
            )
            log_info("Znaleziono przycisk 'Przejdź do ustawień zaawansowanych'.")
            self.observe_before_click(go_advaned_button)

            reject_and_close_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='reject and close']"))
            )
            log_info("Znaleziono przycisk 'Odrzuć i zamknij'.")
            self.observe_before_click(reject_and_close_button)

            email_field = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            self.type_text_with_typo(email_field, "socialflow@op.pl")
            log_info("Wprowadzono adres e-mail.")

            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.sc-d7d238e9-0.kKyUAv"))
            )
            self.observe_before_click(next_button)
            log_info("Kliknięto przycisk 'Dalej' po wprowadzeniu e-maila.")

            password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            self.type_text_with_typo(password_field, "45iPAQkW2uBpTaW")
            log_info("Wprowadzono hasło.")

            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".sc-d7d238e9-0.kKyUAv"))
            )
            self.observe_before_click(next_button)
            log_info("Kliknięto przycisk 'Dalej' po wprowadzeniu hasła.")

            try:
                skip_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[span[text()='Pomiń']]"))
                )
                skip_button.click()
                log_success("Przycisk 'Pomiń' został kliknięty.")
            except Exception as e:
                log_info("Przycisk 'Pomiń' nie jest dostępny, nie został kliknięty.")

            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".folder-item__link.go878900772")))

            driver.execute_script("window.open('https://account.proton.me/mail/signup?plan=free&ref=mail_plus_intro-mailpricing-2', '_blank');")
            driver.switch_to.window(driver.window_handles[1])

            time.sleep(5)

            WebDriverWait(driver, 10).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe[title='Nazwa użytkownika']"))
            )
            log_success("Przełączono kontekst na pierwszy (zewnętrzny) iframe.")

            iframe_html = driver.execute_script("return document.documentElement.outerHTML;")
            print(iframe_html)

            # Znajdź pole `input` wewnątrz wewnętrznego iframe
            username_field = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            log_success("Pole `input` znalezione wewnątrz wewnętrznego iframe.")

            self.type_text_with_typo(username_field, username)
            driver.switch_to.default_content()
            log_info("Wprowadzono nazwę użytkownika oraz wrócono do domyślnego kontekstu.")

            password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            self.type_text_with_typo(password_field, password)
            log_info("Wprowadzono hasło w rejestracji Proton.")

            repeat_password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "repeat-password"))
            )
            self.type_text_with_typo(repeat_password_field, password)
            log_info("Powtórz hasło w rejestracji Proton.")

            create_account_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'button') and contains(text(), 'Utwórz konto')]"))
            )
            self.observe_before_click(create_account_button)
            log_info("Kliknięto przycisk 'Utwórz konto'.")

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".mb-6.color-weak.text-break"))
            )

            try:
                # Czekaj na element i sprawdź jego obecność
                email_verification_select = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "label_1"))
                )
                self.observe_before_click(email_verification_select)
                log_info("Wybrano opcję weryfikacji e-mail.")
            except TimeoutException:
                log_info("Element 'label_1' nie został znaleziony. Przechodzę dalej.")


            username_field = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            self.type_text_with_typo(username_field, username + "@socialflow.33mail.com")
            log_info("Wprowadzono e-mail do weryfikacji.")

            verification_code_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Otrzymaj kod weryfikacyjny')]"))
            )
            time.sleep(5)  # import time
            self.observe_before_click(verification_code_button)
            log_info("Kliknięto przycisk 'Utwórz konto' dla weryfikacji.")

            driver.switch_to.window(driver.window_handles[0])

            current_time = datetime.now()
            one_minute_later = current_time + timedelta(minutes=1)
            two_minute_later = current_time + timedelta(minutes=2)    
            current_time_str = current_time.strftime('%Y-%m-%d %H:%M')
            log_info(current_time_str)
            one_minute_later_str = one_minute_later.strftime('%Y-%m-%d %H:%M')
            log_info(one_minute_later_str)
            two_minute_later_str = two_minute_later.strftime ('%Y-%m-%d %H:%M')

            time.sleep(60)  # import time

            driver.refresh()

            emails = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".mail-list__item"))
            )

            log_info("Główna lista maili na stronie została odnaleziona.")

            for email in emails:
                sender = email.find_element(By.CSS_SELECTOR, ".author-label").text
                log_info("Odnaleziono nadawcę maila: " + sender)
                date_time_str = email.find_element(By.CSS_SELECTOR, ".date-column time").get_attribute("datetime")
                log_info("Data wysłania maila: " + date_time_str)

                if target_email in sender and current_time_str <= date_time_str <= one_minute_later_str:
                    log_success("Znaleziono wiadomość:", sender, date_time_str)
                    email.click()

            verification_code = self.extract_verification_code(driver)

            if verification_code:
                log_success(f"The verification code is: {verification_code}")

                driver.switch_to.window(driver.window_handles[1])

                verification_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "verification"))
                )
                self.type_text_with_typo(verification_field, verification_code)

                verify_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.button.w-full.button-large.button-solid-norm.mt-6"))
                )
                self.observe_before_click(verify_button)

                time.sleep(30)

                self.save_account(email, password)
                log_success(f"Konto Proton zostało utworzone i zapisane jako {email}.")
            else:
                log_error("Nie udało się znaleźć kodu weryfikacyjnego")
        except Exception as e:
            log_error(f"Nie udało się utworzyć konta Proton: {e}")
        finally:
            driver.quit()

class TutanotaBank(EmailBankBase):
    def __init__(self):
        super().__init__(db_name="tutanota_bank.db")
    
    def create_account(self):
        """Automatycznie tworzy nowe konto Tutanota przez stronę."""
        while True:  # Kontynuuj, dopóki użytkownik nie przerwie
            options = webdriver.ChromeOptions()
            driver_path = "C:\\Users\\dawfo\\.wdm\\drivers\\chromedriver\\win64\\130.0.6723.91\\chromedriver-win32\\chromedriver.exe"
            print(f"Zainstalowana wersja chromedrivera: {driver_path}")
            options.add_argument("--incognito")
            options.add_argument("--disable-gpu")
            options.add_argument("--lang=pl-PL")
            driver = webdriver.Chrome(driver_path, options=options)
            
            username = self.generate_username()
            email = f"{username}@tutanota.com"
            password = self.generate_password()
            birthdate = self.generate_birthdate()
            day, month, year = birthdate.split('/')

            try:
                log_info("1")
                driver.get("https://app.tuta.com/login?noAutoLogin=true")

                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//label[contains(@class, 'abs text-ellipsis noselect z1 i pr-s')]"))
                )

                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@title='Zarejestruj się']"))
                ).click()

                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@title='Wybierz' and contains(@class, 'button-content border-radius accent-bg full-width center plr-button flash')]"))
                ).click()

                checkbox1 = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@role='checkbox' and contains(@class, 'pt click flash')]"))
                )
                if checkbox1.get_attribute("aria-checked") == "false":
                    checkbox1.click()

                checkbox2 = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "(//div[@role='checkbox' and contains(@class, 'pt click flash')])[2]"))
                )
                if checkbox2.get_attribute("aria-checked") == "false":
                    checkbox2.click()

                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@title='OK' and contains(@class, 'button-content')]"))
                ).click()

                WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, "//input[@aria-label='Nowe hasło' and @type='password']"))
                ).send_keys(password)
                
                WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, "//input[@aria-label='Powtórz hasło' and @type='password']"))
                ).send_keys(password)

                log_info("2")

                WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, "//input[@aria-label='Adres e-mail' and contains(@class, 'input')]"))
                ).send_keys(username)

                log_info("3")

                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@role='checkbox'][1]"))
                ).click()

                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@role='checkbox'][2]"))
                ).click()

                log_info("4")

                WebDriverWait(driver, 10).until(
                    EC.text_to_be_present_in_element((By.CLASS_NAME, "mt-s"), "Adres e-mail jest dostępny.")
                )

                log_info("5")

                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@title='Następny']"))
                ).click()

                log_info("6")

                time.sleep(5)  # import time

                self.save_account(email, password)
                log_success(f"Konto Tutanota zostało utworzone i zapisane jako {email}.")

            except Exception as e:
                log_error(f"Nie udało się utworzyć konta Tutanota: {e}. Ponawianie próby...")
            finally:
                driver.quit()

class e33emailBank(EmailBankBase):
    def __init__(self):
        super().__init__(db_name="tutanota_bank.db")

    def create_account(self):
        """Automatycznie tworzy nowe konto Posteo przez stronę YouTube, pomijając telefon."""
        options = webdriver.ChromeOptions()
        driver_path = ChromeDriverManager().install()
        print(f"Zainstalowana wersja chromedrivera: {driver_path}")
        options.add_argument("--incognito")
        options.add_argument("--disable-gpu")
        options.add_argument("--lang=pl-PL")
        driver = webdriver.Chrome("C:\\Users\\dawfo\\.wdm\\drivers\\chromedriver\\win64\\130.0.6723.91\\chromedriver-win32\\chromedriver.exe", options=options)
        
        username = self.generate_username()
        email = f"{username}@tutanota.com"
        password = self.generate_password()
        birthdate = self.generate_birthdate()
        day, month, year = birthdate.split('/')

        try:
            log_info("1")
            driver.get("https://33mail.com/signup")

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "lbl-13"))
            ).send_keys(username)

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@title='Zarejestruj się']"))#45iPAQkW2uBpTaW
            ).click()

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@title='Wybierz' and contains(@class, 'button-content border-radius accent-bg full-width center plr-button flash')]"))
            )

            checkbox1 = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@role='checkbox' and contains(@class, 'pt click flash')]"))
            )
            if checkbox1.get_attribute("aria-checked") == "false":
                checkbox1.click()

            # Znalezienie i zaznaczenie drugiego checkboxa
            checkbox2 = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "(//div[@role='checkbox' and contains(@class, 'pt click flash')])[2]"))
            )
            if checkbox2.get_attribute("aria-checked") == "false":
                checkbox2.click()

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@title='OK' and contains(@class, 'button-content')]"))
            )

            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@aria-label='Adres e-mail' and contains(@class, 'input')]"))
            ).send_keys(username)

            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@aria-label='Nowe hasło' and @type='password']"))
            ).send_keys(password)
            
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@aria-label='Powtórz hasło' and @type='password']"))
            ).send_keys(password)

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@role='checkbox'][1]"))
            ).click()

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@role='checkbox'][2]"))
            ).click()

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@title='Następny']"))
            ).click()

            time.sleep(21389454)  # import time

            self.save_account(email, password)
            log_success(f"Konto Tutanota zostało utworzone i zapisane jako {email}.")
        except Exception as e:
            log_error(f"Nie udało się utworzyć konta Tutanota: {e}")
        finally:
            driver.quit()