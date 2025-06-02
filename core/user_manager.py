import asyncio
import sys
import os
import json
import uuid
import aiofiles
from cachetools import TTLCache
from functools import lru_cache
from typing import Dict, List
from core.config_manager import LOCAL_VERSION
from aiohttp import ClientSession, ClientTimeout, ClientResponseError, TCPConnector
from network.firebase_client import check_document_exists, AccountType, save_user_data, verify_user_data, get_user_permissions, FirestoreClient
from cryptography.fernet import Fernet
from utils.utils import log_error, log_info, get_hardware_info

class UserManager:
    instance = None

    ip_cache = TTLCache(maxsize=100, ttl=3600)
    
    GOOGLE_IP_LIST_URL = "gAAAAABnHkhi-lBvqVjhPqwl9HK7I4CvoFuJ1ZouhRauRi_A_IGNi_AXVSBAFPktG0BCD6hZjLqHB9_Jo_wUxIZwx-bdc3iaXvKKYD1OuKHzfeYo1C34rr2MG5W6yPaCOetRIAfXnWaZCwK4pXGKQ1i-ifwn0StkwaSTyQa4IJYN8N_QY0baqnAH0UOFrC0rbcnyO5sEU4DH"
    KEY = "r-tyOCIy_Y1CHVqcEqL5qZPxqOcbYQ_2qjI5Gc0B8YE="
    CACHE_TIMEOUT = 3600
    ENCRYPTED_GOOGLE_IP_LIST_URL = GOOGLE_IP_LIST_URL.encode()
    LOCAL_DATA_FILE = os.path.join(os.path.expanduser("~"), ".config", "user_data.enc")

    def __new__(cls, *args, **kwargs):
        if not cls.instance:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.user_id = None
            self.user_ip = None
            self.sub_id = None
            self.account_type = AccountType.UNAUTHORIZED
            self.authorized_ips = None
            self.last_checked_time = 0
            self.permissions: List[str] = []  # Lista uprawnień użytkownika
            self.decrypt_url()
            self.initialized = True 
    
    async def _create_default_account_data(self) -> Dict:
        """
        Zwraca podstawową konfigurację konta użytkownika w formie słownika,
        który może być zapisany do Firestore.
        """
        hardware_info = get_hardware_info()  # Pobranie informacji o sprzęcie
        data = {
            "sub_id": self.sub_id,              # Jeśli jest, używamy przekazanego sub_id
            "ips": [self.user_ip],              # Lista IP, na którym zarejestrowano konto
            "spec": hardware_info,              # Specyfikacja sprzętu
            "app_version": LOCAL_VERSION,        # Wersja aplikacji
            "active": True,                      # Status aktywności konta
            "permissions": self._get_default_permissions()  # Domyślne uprawnienia
        }
        return data

    def _get_default_permissions(self) -> List[str]:
        """
        Zwraca domyślne uprawnienia na podstawie typu konta.
        Uprawnienia typu admin.* lub worker.* dają dostęp do wszystkich funkcji danej roli.
        """
        if self.account_type == AccountType.ADMIN:
            return ["admin.*"]
        elif self.account_type == AccountType.WORKER:
            return ["worker.*"]
        else:
            return []

    async def _set_file_permissions(self):
        """Ustawia odpowiednie uprawnienia dostępu do pliku w tle."""
        if os.name == 'nt':  # Windows
            os.chmod(self.LOCAL_DATA_FILE, 0o600)
        else:  # Linux/Unix/MacOS
            os.chmod(self.LOCAL_DATA_FILE, 0o600)

    def decrypt_url(self):
        """Odszyfrowuje link do pliku z autoryzowanymi IP."""
        cipher = Fernet(self.KEY)
        self.GOOGLE_IP_LIST_URL = cipher.decrypt(self.ENCRYPTED_GOOGLE_IP_LIST_URL).decode()

    def encrypt_data(self, data: dict) -> bytes:
        """Szyfruje dane użytkownika."""
        cipher = Fernet(self.KEY)
        return cipher.encrypt(json.dumps(data).encode())

    def decrypt_data(self, encrypted_data: bytes) -> dict:
        """Deszyfruje dane użytkownika."""
        cipher = Fernet(self.KEY)
        return json.loads(cipher.decrypt(encrypted_data).decode())

    @lru_cache(maxsize=1)
    async def save_local_data(self):
        """Asynchronicznie zapisuje zaszyfrowane ID użytkownika na urządzeniu."""
        data = {"id": self.user_id}
        encrypted_data = self.encrypt_data(data)
        os.makedirs(os.path.dirname(self.LOCAL_DATA_FILE), exist_ok=True)
        async with aiofiles.open(self.LOCAL_DATA_FILE, "wb") as file:
            await file.write(encrypted_data)
        await self._set_file_permissions()

    @lru_cache(maxsize=1)
    async def load_local_data(self) -> str | None:
        """Asynchronicznie ładuje zaszyfrowane dane użytkownika z urządzenia i zwraca tylko ID."""
        if not os.path.exists(self.LOCAL_DATA_FILE):
            return None
        async with aiofiles.open(self.LOCAL_DATA_FILE, "rb") as file:
            encrypted_data = await file.read()
        decrypted_data = self.decrypt_data(encrypted_data)
        return decrypted_data.get("id")

    async def fetch_authorized_ips(self, session: ClientSession) -> dict:
        """Pobiera listę autoryzowanych IP z zewnętrznego źródła."""
        current_time = asyncio.get_event_loop().time()
        if self.authorized_ips is None or (current_time - self.last_checked_time) > self.CACHE_TIMEOUT:
            try:
                async with session.get(self.GOOGLE_IP_LIST_URL) as response:
                    response.raise_for_status()
                    response_data = await response.text()
                    self.authorized_ips = json.loads(response_data)
                    self.last_checked_time = current_time
            except ClientResponseError as e:
                log_error(f"Błąd podczas pobierania listy IP: {e}")
                return {"admin_ips": [], "worker_ips": []}
            except Exception as e:
                log_error(f"Błąd ogólny: {e}")
                return {"admin_ips": [], "worker_ips": []}
        return self.authorized_ips

    async def get_user_ip(self, session: ClientSession) -> str | None:
        """Pobiera adres IP użytkownika, używając pamięci podręcznej i alternatywnego źródła."""
        if 'user_ip' in self.ip_cache:
            return self.ip_cache['user_ip']
        try:
            async with session.get('https://api.ipify.org') as response:
                response.raise_for_status()
                ip = await response.text()
                if not ip:
                    raise ValueError("Pusty adres IP zwrócony przez api.ipify.org")
                self.ip_cache['user_ip'] = ip
                return ip
        except Exception as e:
            log_error(f"Błąd podczas pobierania IP z api.ipify.org: {e}")
            try:
                async with session.get('https://httpbin.org/ip') as response:
                    response.raise_for_status()
                    ip_data = await response.json()
                    ip = ip_data.get('origin')
                    if not ip:
                        raise ValueError("Pusty adres IP zwrócony przez httpbin.org")
                    self.ip_cache['user_ip'] = ip
                    return ip
            except Exception as e:
                log_error(f"Błąd podczas pobierania IP z httpbin.org: {e}")
                return None
    
    async def check_ip(self, session: ClientSession):
        """Asynchronicznie sprawdza IP użytkownika i dane użytkownika w Firestore."""
        try:
            user_ip, authorized_ips = await asyncio.gather(
                self.get_user_ip(session),
                self.fetch_authorized_ips(session)
            )
            if not user_ip:
                log_error("Nie udało się pobrać adresu IP użytkownika.")
                return AccountType.UNAUTHORIZED
            if user_ip in authorized_ips.get("admin_ips", []):
                return AccountType.ADMIN
            elif user_ip in authorized_ips.get("worker_ips", []):
                return AccountType.WORKER
        except Exception as e:
            log_error(f"Błąd podczas sprawdzania IP: {e}")
            return AccountType.UNAUTHORIZED

    async def verify_local_data(self, default_account_data) -> AccountType:
        """Ładuje i weryfikuje dane użytkownika równolegle."""
        self.user_id = await self.load_local_data()
        if not self.user_id:
            return AccountType.UNAUTHORIZED
        async with FirestoreClient() as client:
            session = client.session

            account_type, user_ip = await asyncio.gather(
                verify_user_data(client, self.user_id, self.user_ip, default_account_data),
                self.get_user_ip(session)
            )
            self.user_ip = user_ip
            await self.check_ip(session)
            if account_type == "admin":
                return AccountType.ADMIN
            elif account_type == "worker":
                return AccountType.WORKER
            else:
                return AccountType.UNAUTHORIZED

    async def register_user(self):
        """Rejestruje użytkownika w odpowiedniej kolekcji na podstawie uprawnień."""
        user_input = input("Podaj swoje subID (nazwa dokumentu w Firestore): ").strip()
        self.sub_id = user_input if user_input else None
        self.user_id = str(uuid.uuid4())
        async with ClientSession(timeout=ClientTimeout(total=10)) as session:
            # Ustalamy typ konta na podstawie IP przed stworzeniem danych konta
            self.account_type = await self.check_ip(session)
            if self.account_type == AccountType.ADMIN:
                collection = "admins"
            elif self.account_type == AccountType.WORKER:
                collection = "workers"
            else:
                log_error("Nieautoryzowany użytkownik. Nie zapisuję do Firestore.")
                return
            # Tworzymy dane konta z domyślnymi uprawnieniami
            data = await self._create_default_account_data()
            await self.save_local_data()
            if self.sub_id:
                document_exists = await check_document_exists(session, self.user_id, collection)
                if document_exists:
                    log_error("Dokument o podanej nazwie już istnieje. Podaj inną nazwę subID:")
                    self.sub_id = input("Nowa nazwa subID: ").strip()
                    document_exists = await check_document_exists(session, self.user_id, collection)
                    if document_exists:
                        log_error("Nie udało się znaleźć unikalnego subID.")
                        return
            await save_user_data(session, self.user_id, self.sub_id, data, collection)
            new_permissions = await get_user_permissions(session, collection, self.user_id)
            self.update_permissions(new_permissions)


    async def run(self) -> AccountType:
        async with ClientSession(timeout=ClientTimeout(total=10)) as session:
            self.user_ip = await self.get_user_ip(session)
            default_account_data = await self._create_default_account_data()
            self.account_type = await self.verify_local_data(default_account_data)
            
            # Jeśli dane lokalne zostały zweryfikowane, pobieramy uprawnienia
            if self.account_type != AccountType.UNAUTHORIZED:
                collection = "admins" if self.account_type == AccountType.ADMIN else "workers"
                new_permissions = await get_user_permissions(session, collection, self.user_id)
                self.update_permissions(new_permissions)
                #update_user_data(session, self.user_id, self.sub_id, [], self.account_type)
                return self.account_type, self.user_id
            
            # Reszta logiki rejestracji, gdy dane lokalne nie są zweryfikowane
            if not self.user_ip:
                log_error("Nie udało się pobrać IP użytkownika.")
                self.self_destruct()
                return AccountType.UNAUTHORIZED
            self.account_type = await self.check_ip(session)
            if self.account_type == AccountType.UNAUTHORIZED:
                log_error("Nieautoryzowane IP. Program zostanie zamknięty.")
                await asyncio.sleep(3)
                self.self_destruct()
                return self.account_type, self.user_id
            
            log_info("Pierwsze uruchomienie. Rejestracja użytkownika...")
            await self.register_user()
            return self.account_type, self.user_id


    def self_destruct(self):
        """Usuwa program z systemu, jeśli IP jest nieautoryzowane."""
        program_path = sys.argv[0]
        if os.name == 'nt':  # Windows
            os.system(f"start /min del /f /q {program_path}")
        else:  # Linux/Unix/MacOS
            os.system(f'rm -f {program_path}')
        sys.exit("Program został usunięty.")

    def has_permission(self, permission: str) -> bool:
        """
        Sprawdza, czy użytkownik ma podane uprawnienie, uwzględniając wildcardy i ewentualne wyłączenia.
        Przykład: uprawnienie "admin.create_tasks" będzie zwracać True, jeśli na liście uprawnień znajduje się "admin.*"
        i nie jest wyłączone przez "-admin.create_tasks".
        """
        if not self.permissions:
            return False
        # Sprawdzenie wykluczeń
        if f"-{permission}" in self.permissions:
            return False
        # Sprawdzenie bezpośredniej zgody
        if permission in self.permissions:
            return True
        # Sprawdzenie uprawnień z wildcardem (np. "admin.*")
        parts = permission.split('.')
        if len(parts) > 1:
            wildcard = parts[0] + ".*"
            if wildcard in self.permissions:
                return True
        return False

    def update_permissions(self, new_permissions: List[str]):
        """
        Aktualizuje listę uprawnień użytkownika.
        Umożliwia łatwą modyfikację uprawnień (np. przez inny moduł) przy starcie aplikacji.
        """
        self.permissions = new_permissions