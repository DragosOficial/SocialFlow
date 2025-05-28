import os
import random
import string
import time
import json
import calendar  # Do obliczania liczby dni w miesiącu
import webbrowser
import pyperclip
import keyboard
import asyncio
from datetime import datetime, timezone
from aiohttp import ClientSession
from enum import Enum
from utils.utils import log_info, log_success, log_error, storage_bucket, db
from network import firebase_client

class Google:
    def __init__(self, platform="Google"):
        self.platform = platform
        self.account_data = {}

    def generate_random_string(self, length=10):
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def get_random_name(self, collection):
        # Jeżeli baza danych nie jest dostępna, używamy przykładowych imion/ nazwisk.
        try:
            docs = db.collection(collection).stream()
            names = [doc.to_dict() for doc in docs]
            if names:
                random_doc = random.choice(names)
                return random_doc.get("original_name", "Imie")
            else:
                return "Imie"
        except Exception:
            return random.choice(["Jan", "Piotr"])
        
    def get_random_recovery_mail(self):
        try:
            docs = db.collection("mail_database").stream()
            mails_with_count = []
            for doc in docs:
                data = doc.to_dict()
                email = data.get("email")
                if email:
                    # Jeśli dokument nie posiada pola recovery_count, domyślnie przyjmujemy 0.
                    recovery_count = data.get("recovery_count", 0)
                    mails_with_count.append((email, recovery_count))
            if mails_with_count:
                # Znalezienie minimalnej wartości recovery_count
                min_count = min(count for _, count in mails_with_count)
                # Wybranie tych dokumentów, które mają minimalną wartość recovery_count
                candidates = [email for email, count in mails_with_count if count == min_count]
                return random.choice(candidates)
            else:
                return "N/A"
        except Exception as e:
            log_error(f"Nie można pobrać recovery_mail z mail_database: {e}")
            return "N/A"

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
        Wypełnia dane urodzenia i płeć.
        Dla naszych potrzeb kopiujemy tylko dzień i rok daty urodzenia.
        """
        day, month, year = self.generate_birthdate()
        # Zapis pełnej daty urodzenia (DD-MM-YYYY) do wyświetlenia w konsoli
        self.account_data["birth_date"] = f"{day:02d}.{month:02d}.{year}"
        # Do kopiowania – tylko dzień i rok
        self.account_data["birth_day"] = str(day)
        self.account_data["birth_year"] = str(year)
        self.account_data["gender"] = "Mężczyzna"

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

    async def confirm_account(self) -> bool:
        """
        Prosi użytkownika o potwierdzenie:
        - Naciśnięcie Enter potwierdza, że konto jest poprawne.
        - Wpisanie "esc" potwierdza anulowanie.
        """
        user_input = (await asyncio.to_thread(input, 
            "Czy konto zostało poprawnie stworzone? (naciśnij Enter, aby zatwierdzić, lub wpisz 'esc' aby anulować): ")).strip()
        if user_input == "":
            log_info("Konto zostało zatwierdzone.")
            return True
        elif user_input.lower() == "esc":
            log_info("Konto zostało anulowane.")
            return False
        else:
            log_error("Nieprawidłowy wybór, spróbuj ponownie.")
            return await self.confirm_account()

    async def generate_account(self, task_id, user_id):
        # Generowanie danych konta
        first_name = self.get_random_name("names_database")
        last_name = self.get_random_name("last_names_database")
        self.account_data["first_name"] = first_name
        self.account_data["last_name"] = last_name

        # Normalizacja imienia i nazwiska
        first_name_norm = self.normalize_name(first_name)
        last_name_norm = self.normalize_name(last_name)
        recovery_mail = self.get_random_recovery_mail()
        combined = first_name_norm + last_name_norm

        if len(combined) < 2:
            username_core = combined
        else:
            # Wstawianie kropek na dwóch losowych pozycjach
            positions = random.sample(range(1, len(combined)), 2)
            positions.sort()
            p1, p2 = positions
            username_core = combined[:p1] + '.' + combined[p1:p2] + '.' + combined[p2:]
        digits = random.randint(10, 99)
        username = f"{username_core}{digits}"
        email = f"{username}@gmail.com"
        password = self.generate_random_string(12)

        self.account_data["username"] = username
        self.account_data["email"] = email
        self.account_data["password"] = password

        # Wypełnienie daty urodzenia i płci
        self.fill_birthdate_and_gender()

        # Wyświetlenie wszystkich wygenerowanych danych w konsoli
        print("Wygenerowane dane konta:")
        print(f"Imię: {first_name}")
        print(f"Nazwisko: {last_name}")
        print(f"Nazwa użytkownika: {username}")
        print(f"E-mail: {email}")
        print(f"Hasło: {password}")
        print(f"Data urodzenia (DD-MM-YYYY): {self.account_data['birth_date']}")
        print(f"Płeć: {self.account_data['gender']}")
        print(f"Mail Recovery: {recovery_mail}")

        # Pytamy użytkownika o potwierdzenie
        confirmed = await self.confirm_account()
        if confirmed:
            await self.save_to_firebase(email, password, recovery_mail, task_id, first_name_norm, last_name_norm)
        else:
            log_info("Zapis do Firestore został anulowany.")
            return False

    async def confirm_account(self) -> bool:
        """
        Prosi użytkownika o potwierdzenie:
        - Dwukrotne naciśnięcie Enter potwierdza, że konto jest poprawne.
        - Dwukrotne wpisanie "esc" potwierdza anulowanie.
        """
        while True:
            # Pierwsze potwierdzenie
            user_input = (await asyncio.to_thread(input, 
                "Czy konto zostało poprawnie stworzone? (naciśnij Enter aby zatwierdzić, lub wpisz 'esc' aby anulować): ")).strip()
            if user_input == "":
                log_info("Potwierdzono jednokrotnie.")
                # Drugie potwierdzenie
                user_input2 = (await asyncio.to_thread(input, 
                    "Potwierdź zatwierdzenie (naciśnij Enter ponownie): ")).strip()
                if user_input2 == "":
                    log_info("Potwierdzono dwukrotnie.")
                    return True
                else:
                    log_error("Potwierdzenie nie powiodło się, spróbuj ponownie.")
            elif user_input.lower() == "esc":
                log_info("Anulowanie jednokrotnie.")
                user_input2 = (await asyncio.to_thread(input, 
                    "Potwierdź anulowanie (wpisz 'esc' ponownie): ")).strip()
                if user_input2.lower() == "esc":
                    log_info("Anulowanie dwukrotnie.")
                    return False
                else:
                    log_error("Potwierdzenie anulowania nie powiodło się, spróbuj ponownie.")
            else:
                log_error("Nieprawidłowy wybór, spróbuj ponownie.")


    async def confirm_cookies(self, service: str) -> bool:
        """
        Prosi użytkownika o potwierdzenie, czy pliki cookies dla danego serwisu
        są zapisane w odpowiednim pliku.
        - Naciśnięcie Enter potwierdza poprawność.
        - Wpisanie "esc" potwierdza anulowanie.
        """
        inp = (await asyncio.to_thread(input, 
            f"Czy pliki cookies dla {service} są zapisane w odpowiednim pliku? (naciśnij Enter, aby potwierdzić, lub wpisz 'esc' aby anulować): ")).strip()
        if inp == "":
            log_info(f"Pliki cookies dla {service} zostały zatwierdzone.")
            return True
        elif inp.lower() == "esc":
            log_info(f"Anulowano potwierdzenie dla {service}.")
            return False
        else:
            log_error(f"Nieprawidłowy wybór dla {service}, spróbuj ponownie.")
            return await self.confirm_cookies(service)

    async def save_to_firebase(self, email, password, recovery_mail, task_id, first_name, last_name):
        # Przygotowanie danych sesji bez informacji z przeglądarki
        session_data = {
            "email": email,
            "password": password,
            "user_agent": "N/A",
            "cookies": []  # Tu będziemy przechowywać listę ścieżek do plików cookies
        }

        # Tworzenie sub_id na podstawie e-maila
        cut_email = email.split("@")[0]
        
        # Definiujemy kolejność potwierdzania: najpierw YouTube, potem Google, na końcu Gmail
        services_order = ["YouTube", "Google", "Gmail"]
        # Mapowanie serwisów na lokalne pliki cookies (jeśli plik nie istnieje, zostanie utworzony)
        cookies_info_files = {
            "Google": "cookies_for_sm_google.txt",
            "YouTube": "cookies_for_sm_youtube.txt",
            "Gmail": "cookies_for_sm_gmail.txt"
        }
        # Lista docelowych ścieżek zapisu w Storage – zgodnie z wymaganą kolejnością:
        # indeks 0: Google, indeks 1: YouTube, indeks 2: Gmail
        cookies_file_paths = [
            f"Session Manager/Google/{cut_email}.json",   # Google
            f"Session Manager/YouTube/{cut_email}.json",    # YouTube
            f"Session Manager/Gmail/{cut_email}.json"       # Gmail
        ]
        
        cookies_contents = []  # Lista na zawartość cookies dla każdego serwisu

        # Pytamy o cookies w kolejności: YouTube, Google, Gmail
        for service in services_order:
            file_path = cookies_info_files[service]
            if not os.path.exists(file_path):
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("[]")
                log_info(f"Plik {file_path} nie istniał, został utworzony.")
            confirmed = await self.confirm_cookies(service)
            if confirmed:
                with open(file_path, "r", encoding="utf-8") as f:
                    cookies_data = json.load(f)
                log_info(f"Konwersja na plik session managera dla {service} w toku...")
                await asyncio.sleep(random.uniform(1, 2))
                cookies_contents.append(cookies_data)
                log_success(f"Konwersja zakończona dla {service}.")
            else:
                log_info("Zapis do Firestore został anulowany przez użytkownika.")
                return False

        # Wgrywamy pliki cookies do Storage – zgodnie z ustaloną kolejnością
        # Uwaga: Kolejność w cookies_file_paths to [Google, YouTube, Gmail],
        # ale potwierdzaliśmy w kolejności [YouTube, Google, Gmail].
        # Dlatego dopasowujemy indeksy:
        service_order_to_index = {"Google": 0, "YouTube": 1, "Gmail": 2}
        for service in ["Google", "YouTube", "Gmail"]:
            idx = service_order_to_index[service]
            destination_path = cookies_file_paths[idx]
            cookies_json = json.dumps(cookies_contents[idx], default=str)
            blob = storage_bucket.blob(destination_path)
            blob.upload_from_string(cookies_json, content_type="application/json")
            log_info(f"Plik cookies dla {service} został zapisany do {destination_path}.")
            try:
                os.remove(cookies_info_files[service])
                log_info(f"Plik {cookies_info_files[service]} został usunięty.")
            except Exception as e:
                log_error(f"Nie udało się usunąć pliku {cookies_info_files[service]}: {e}")

        # Zapisujemy listę ścieżek do plików cookies w session_data
        session_data["cookies"] = cookies_file_paths

        # Przygotowanie danych do zapisania w Firestore – dodajemy klucz "platform"
        data = {
            "email": email,
            "password": password,
            "first_name": self.account_data.get("first_name"),
            "last_name": self.account_data.get("last_name"),
            "birth_date": self.account_data.get("birth_date"),
            "gender": self.account_data.get("gender"),
            "user_agent": session_data["user_agent"],
            "cookies": session_data["cookies"],
            "platform": self.platform,
            "recovery_mail": recovery_mail,
            "recovery_count": 0,
            "account_registered": [],
            "task_id": task_id
        }

        async with ClientSession() as session:
            await asyncio.gather(
                firebase_client.save_user_data(session, cut_email, cut_email, data, "mail_database"),
                firebase_client.increment_recovery_count(recovery_mail),
                firebase_client.increment_count(first_name, "names_database", "count"),
                firebase_client.increment_count(last_name, "last_names_database", "count")
            )

        log_success(f"Konto zapisane w Firebase: {email}")