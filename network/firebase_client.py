import os
import json
import requests
import asyncio
import aiohttp
from typing import Dict
from datetime import datetime, timezone, timedelta
from enum import Enum
from aiohttp import ClientSession, ClientError
from utils.utils import log_error, log_info, log_success, get_hardware_info, clear_console
from core.config_manager import LOCAL_VERSION
from utils.banks import AccountType
from network.updater import check_for_updates
from automation.social_media import TikTok
from automation.email_account import Google
from utils.tasks import TaskType

# Wczytanie klucza admin z pliku JSON
FIREBASE_ADMIN_KEY_PATH = os.getenv("FIREBASE_ADMIN_KEY_PATH")
with open(FIREBASE_ADMIN_KEY_PATH, 'r') as key_file:
    admin_key = json.load(key_file)

# Wartości z klucza admin
PRIVATE_KEY = admin_key["private_key"]
PROJECT_ID = admin_key["project_id"]

# URL do Firestore
FIRESTORE_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

TASK_TYPE_HANDLERS = {
    TaskType.CHECK_FOR_UPDATES: check_for_updates,
    TaskType.TT_COPY_ACCOUNT_DATA: TikTok().copy_accounts,
    TaskType.TT_MASS_REPORT: TikTok().mass_report,
    TaskType.G_GENERATE_ACCOUNT: Google().generate_account,
    #TaskType.GENERATE_ACCOUNT: handle_generate_account,
}

# Optymalizacja połączenia
async def check_connection(session: ClientSession):
    """Sprawdza połączenie z Firestore za pomocą REST API i klucza admin."""
    try:
        test_url = f"{FIRESTORE_BASE_URL}/users?key={PRIVATE_KEY}"
        #log_info(test_url)
        async with session.get(test_url) as response:
            if response.status == 200:
                log_info("Połączenie z Firestore działa poprawnie.")
            elif response.status == 404:
                log_error("Połączenie działa, ale wskazana kolekcja lub dokument nie istnieje.")
            else:
                log_error(f"Błąd połączenia z Firestore: {response.status} - {await response.text()}")
    except ClientError as e:
        log_error(f"Błąd połączenia: {str(e)}")

def format_firestore_data(data: dict) -> dict:
    """Formatuje dane do formatu Firestore (JSON API)."""
    return {
        key: {"booleanValue" if isinstance(value, bool) else "stringValue" if isinstance(value, str) else "timestampValue": value if not isinstance(value, datetime) else value.isoformat() + "Z"}
        for key, value in data.items()
    }

# Sprawdzanie dokumentu asynchronicznie
async def document_exists(session: ClientSession, collection: str, doc_id: str) -> bool:
    """Sprawdza, czy dokument istnieje w Firestore."""
    url = f"{FIRESTORE_BASE_URL}/{collection}/{doc_id}?key={PRIVATE_KEY}"
    try:
        async with session.get(url) as response:
            return response.status == 200
    except ClientError as e:
        log_error(f"Błąd sprawdzania istnienia dokumentu: {str(e)}")
        return False

# Asynchroniczna funkcja do tworzenia lub aktualizowania dokumentów
async def create_or_update_document(session: ClientSession, collection: str, doc_id: str, data: dict):
    """Tworzy lub aktualizuje dokument w Firestore."""
    url = f"{FIRESTORE_BASE_URL}/{collection}/{doc_id}?key={PRIVATE_KEY}"
    
    try:
        if await document_exists(session, collection, doc_id):
            update_data = {"fields": {"active": {"booleanValue": True}}}
            async with session.patch(url, json=update_data) as response:
                if response.status in {200, 201}:
                    log_info(f"Dokument '{doc_id}' został zaktualizowany.")
                else:
                    log_error(f"Błąd aktualizacji dokumentu: {response.status} - {await response.text()}")
        else:
            async with session.patch(url, json={"fields": data}) as response:
                if response.status in {200, 201}:
                    log_info(f"Dokument '{doc_id}' został zapisany.")
                else:
                    log_error(f"Błąd tworzenia dokumentu: {response.status} - {await response.text()}")
    except ClientError as e:
        log_error(f"Błąd połączenia z Firestore: {str(e)}")

async def fetch_active_workers(session: ClientSession):
    """
    Pobiera wszystkich użytkowników typu WORKER, którzy mają 'active' ustawione na True.
    :param session: Instancja aiohttp.ClientSession do obsługi zapytań HTTP.
    :return: Lista aktywnych pracowników.
    """
    url = f"{FIRESTORE_BASE_URL}/workers?key={PRIVATE_KEY}"
    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                workers = data.get("documents", [])
                active_workers = []

                for worker in workers:
                    fields = worker.get("fields", {})
                    is_active = fields.get("active", {}).get("booleanValue", False)
                    
                    if is_active:
                        active_workers.append(worker)

                return active_workers
            else:
                log_error(f"Błąd podczas pobierania WORKER: {response.status} - {await response.text()}")
                return []
    except ClientError as e:
        log_error(f"Błąd podczas łączenia z Firestore: {str(e)}")
        return []


async def set_account_state(user_id: str, account_type: AccountType, is_active: bool) -> None:
    """Ustawia konto jako aktywne lub nieaktywne w Firestore w zależności od podanego account_type.
       Jeśli zmienna `active` już ma docelową wartość, nic nie zmienia.
    """
    
    # Jeśli podano typ konta, używamy tylko jednej kolekcji, w przeciwnym razie sprawdzamy obie.
    collections = [account_type.value] if account_type else [AccountType.ADMIN.value, AccountType.WORKER.value]
    update_data = {"fields": {"active": {"booleanValue": is_active}}}
    params = {"updateMask.fieldPaths": "active"}  # Aktualizujemy tylko `active`

    async with aiohttp.ClientSession() as session:
        for collection in collections:
            doc_url = f"{FIRESTORE_BASE_URL}/{collection}/{user_id}?key={PRIVATE_KEY}"

            try:
                # Pobierz aktualne dane użytkownika
                async with session.get(doc_url) as doc_response:
                    if doc_response.status == 200:
                        doc_data = await doc_response.json()
                        current_active = doc_data.get("fields", {}).get("active", {}).get("booleanValue")

                        # Jeśli wartość `active` już jest taka sama, nic nie zmieniamy
                        if current_active == is_active:
                            log_info(f"Konto '{user_id}' ({collection}) już ma wartość active={is_active}. Pominięto aktualizację.")
                            return

                    elif doc_response.status == 404:
                        continue  # Sprawdzamy kolejną kolekcję

                # Aktualizujemy `active`, jeśli trzeba
                async with session.patch(doc_url, json=update_data, params=params) as response:
                    if response.status == 200:
                        state_str = "aktywne" if is_active else "nieaktywne"
                        log_info(f"Konto '{user_id}' ({collection}) zostało oznaczone jako {state_str}.")
                        return

                    log_error(f"Błąd aktualizacji statusu ({collection}): {response.status} - {await response.text()}")
                    return  # Nie próbujemy kolejnej kolekcji, skoro użytkownik tu istniał

            except aiohttp.ClientError as e:
                log_error(f"Błąd połączenia ({collection}): {e}")
                return  # Nie kontynuujemy w przypadku problemów z połączeniem

    log_error(f"Nie znaleziono użytkownika '{user_id}' w kolekcji '{account_type.name if account_type else 'admin & worker'}'.")


def cleanup_loop(user_id, account_type):
    """Funkcja uruchamiana przy zamykaniu aplikacji."""
    try:
        asyncio.get_running_loop().stop()
    except:
        pass

    asyncio.run(set_account_state(user_id, account_type, False))

async def cleanup(user_id, account_type):
    """Funkcja uruchamiana przy zamykaniu aplikacji.
    Teraz jest asynchroniczna – zamiast używać asyncio.run(), po prostu oczekuje na set_account_state."""
    try:
        await set_account_state(user_id, account_type, False)
    except Exception as e:
        log_error(f"Cleanup error: {e}")


async def create_task(session: ClientSession, task_type, assigned_ids: list, date: str = None, 
                      assigned_by_id: str = None, assigned_by_ip: str = None, special_attributes: dict = None):
    """Tworzy zadanie w Firestore z opcjonalną datą."""
    try:
        if not assigned_ids:
            log_error("Pole 'assigned_ids' jest wymagane do utworzenia zadania.")
            return

        # Zbieranie daty i godziny zlecenia
        existing_tasks = await fetch_existing_tasks(session)
        next_task_number = determine_next_task_number(existing_tasks)
        document_name = f"task{next_task_number}"

        assigned_time = datetime.now(timezone.utc)
        assigned_at_seconds = int(assigned_time.timestamp())
        assigned_at_nanos = assigned_time.microsecond * 1000

        # Przygotowanie danych zadania – dodano cancelled_ids jako pustą listę
        # Ustawiamy task type jako "TaskType.{wartość}"
        if hasattr(task_type, "value"):
            task_type_str = f"TaskType.{task_type.value}"
        else:
            task_type_str = f"TaskType.{task_type}"
            
        data = {
            "type": {"stringValue": task_type_str},
            "assigned_ids": {"arrayValue": {"values": [{"stringValue": str(id)} for id in assigned_ids]}},
            "completed_ids": {"arrayValue": {"values": []}},
            "cancelled_ids": {"arrayValue": {"values": []}},
            "assigned_by_id": {"stringValue": assigned_by_id},
            "assigned_by_ip": {"stringValue": assigned_by_ip},
            "assigned_at": {"timestampValue": {"seconds": assigned_at_seconds, "nanos": assigned_at_nanos}},
        }

        # Jeśli 'date' jest podane, konwertujemy na timestamp
        if date is not None:
            try:
                date_time = datetime.fromisoformat(date)
                date_seconds = int(date_time.timestamp())
                date_nanos = date_time.microsecond * 1000
                data["date"] = {"timestampValue": {"seconds": date_seconds, "nanos": date_nanos}}
            except (ValueError, TypeError):
                log_error(f"Niepoprawny format daty: {date}, ustawiono bieżący czas.")
                data["date"] = {"timestampValue": {"seconds": assigned_at_seconds, "nanos": assigned_at_nanos}}
        else:
            data["date"] = {"timestampValue": {"seconds": assigned_at_seconds, "nanos": assigned_at_nanos}}

        if special_attributes:
            for key, value in special_attributes.items():
                data[key] = {"stringValue": value}

        url = f"{FIRESTORE_BASE_URL}/tasks/{document_name}?key={PRIVATE_KEY}"
        async with session.patch(url, json={"fields": data}) as response:
            if response.status in {200, 201}:
                log_success(f"Zadanie {task_type_str} zostało utworzone z nazwą {document_name}.")
            else:
                log_error(f"Błąd podczas tworzenia zadania: {response.status} - {await response.text()}")
    except Exception as e:
        log_error(f"Błąd podczas tworzenia zadania: {str(e)}")

async def fetch_existing_tasks(session: ClientSession) -> list:
    """Pobiera istniejące dokumenty z kolekcji tasks."""
    url = f"{FIRESTORE_BASE_URL}/tasks?key={PRIVATE_KEY}"
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            # Użyj await, aby poczekać na wynik odpowiedzi
            return (await response.json()).get("documents", [])
    except ClientError as e:
        log_error(f"Błąd podczas pobierania zadań: {str(e)}")
        return []

def determine_next_task_number(existing_tasks: list) -> int:
    """Określa kolejny numer dokumentu na podstawie istniejących nazw."""
    task_numbers = []
    for task in existing_tasks:
        # Oczekujemy nazw w formacie "taskX", gdzie X to liczba
        name = task["name"].split("/")[-1]
        if name.startswith("task") and name[4:].isdigit():
            task_numbers.append(int(name[4:]))
    return max(task_numbers, default=0) + 1

def format_task_data(task_type: str, special_attributes: dict) -> dict:
    """Formatuje dane zadania do wysłania do Firestore."""
    return {
        "task_type": {"stringValue": str(task_type)},
        **{key: {"stringValue": str(value)} for key, value in special_attributes.items()}
    }

async def get_active_workers(session: ClientSession) -> list:
    """
    Pobiera listę aktywnych pracowników z kolekcji 'workers'.
    Nazwa dokumentu to UUID, a pobierany jest sub_id.
    
    :param session: Instancja aiohttp.ClientSession do obsługi zapytań HTTP.
    :return: Lista słowników zawierających sub_id i UUID.
    """
    url = f"{FIRESTORE_BASE_URL}/workers?key={PRIVATE_KEY}"
    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                workers = data.get("documents", [])
                active_workers = []

                for worker in workers:
                    fields = worker.get("fields", {})
                    is_active = fields.get("active", {}).get("booleanValue", False)
                    sub_id = fields.get("sub_id", {}).get("stringValue", "")
                    id = worker.get("name", "").split("/")[-1]  # Nazwa dokumentu to UUID

                    if is_active and sub_id:
                        active_workers.append({"sub_id": sub_id, "id": id})

                return active_workers
            else:
                log_error(f"Błąd podczas pobierania pracowników: {response.status} - {await response.text()}")
                return []
    except ClientError as e:
        log_error(f"Błąd podczas łączenia z Firestore: {str(e)}")
        return []
    
async def check_document_exists(session: ClientSession, user_id: str, collection: str) -> bool:
    """Sprawdza, czy dokument o danym sub_id już istnieje w Firestore."""
    url = f"{FIRESTORE_BASE_URL}/{collection}/{user_id}?key={PRIVATE_KEY}"
        
    try:
        async with session.get(url) as response:
            if response.status == 200:
                return True  # Dokument istnieje
            elif response.status == 404:
                return False  # Dokument nie istnieje
            else:
                log_error(f"Błąd podczas sprawdzania dokumentu: {await response.text()}")
                return False
    except ClientError as e:
        log_error(f"Błąd połączenia z Firestore: {str(e)}")
        return False
    

async def increment_recovery_count(mail: str):
    """
    Pobiera dokument o danym mailu z kolekcji mail_database i zwiększa jego recovery_count o 1.
    Usuwa wszystko po znaku "@" z przekazanego maila.
    """
    try:
        # Używamy tylko części przed znakiem "@" jako identyfikatora dokumentu
        doc_id = mail.split("@")[0]
        async with ClientSession() as session:
            url = f"{FIRESTORE_BASE_URL}/mail_database/{doc_id}?key={PRIVATE_KEY}"
            # Pobranie aktualnego dokumentu wraz ze wszystkimi polami
            async with session.get(url) as response:
                if response.status == 200:
                    doc = await response.json()
                    fields = doc.get("fields", {})
                    # Pobranie bieżącej wartości recovery_count, domyślnie 0
                    current_count = int(fields.get("recovery_count", {}).get("integerValue", "0"))
                    new_count = current_count + 1
                else:
                    log_error(f"Nie udało się pobrać dokumentu dla {mail}: {await response.text()}")
                    return
            # Aktualizacja pola recovery_count w już pobranych polach
            fields["recovery_count"] = {"integerValue": str(new_count)}
            update_data = {
                "fields": fields  # Zastępujemy wszystkie istniejące pola
            }
            async with session.patch(url, json=update_data) as patch_response:
                if patch_response.status == 200:
                    log_success(f"Zwiększono recovery_count dla {mail} do {new_count}.")
                else:
                    log_error(f"Błąd aktualizacji recovery_count: {await patch_response.text()}")
    except Exception as e:
        log_error(f"Błąd podczas inkrementacji recovery_count: {e}")


async def increment_count(name: str, collection: str, field: str):
    """
    Pobiera dokument o danym imieniu lub nazwisku z kolekcji określonej przez 'collection'
    i zwiększa wartość pola o nazwie podanej w parametrze 'field' o 1.
    Używa nazwy (zmienionej na lowercase, z pierwszą literą wielką) jako identyfikatora dokumentu.
    """
    try:
        # Używamy nazwy (lowercase, następnie capitalize) jako identyfikatora dokumentu
        doc_id = name.lower()
        async with ClientSession() as session:
            url = f"{FIRESTORE_BASE_URL}/{collection}/{doc_id}?key={PRIVATE_KEY}"
            # Pobranie aktualnego dokumentu
            async with session.get(url) as response:
                if response.status == 200:
                    doc = await response.json()
                    fields = doc.get("fields", {})
                    # Pobranie bieżącej wartości pola 'field', domyślnie 0
                    current_count = int(fields.get(field, {}).get("integerValue", "0"))
                    new_count = current_count + 1
                else:
                    log_error(f"Nie udało się pobrać dokumentu dla {name}: {await response.text()}")
                    return
            
            # Aktualizacja pola o nazwie przekazanej w 'field'
            fields[field] = {"integerValue": str(new_count)}
            update_data = {
                "fields": fields  # Zastępujemy wszystkie istniejące pola dokumentu
            }
            async with session.patch(url, json=update_data) as patch_response:
                if patch_response.status == 200:
                    log_success(f"Zwiększono {field} dla {name} do {new_count}.")
                else:
                    log_error(f"Błąd aktualizacji {field} dla {name}: {await patch_response.text()}")
    except Exception as e:
        log_error(f"Błąd podczas inkrementacji {field} dla {name}: {e}")


async def save_user_data(session: ClientSession, user_id: str, sub_id: str, data: dict, collection: str):
    """Zapisuje dane użytkownika do odpowiedniej kolekcji w Firestore."""
    
    # Uzupełnienie pola uprawnień, jeśli nie zostało przekazane
    if "permissions" not in data:
        if collection == "admins":
            data["permissions"] = ["admin.*"]
        elif collection == "workers":
            data["permissions"] = ["worker.*"]
    
    url = f"{FIRESTORE_BASE_URL}/{collection}/{user_id}?key={PRIVATE_KEY}"
    
    # Przygotowanie danych do zapisu w Firestore
    fields = {}
    for key, value in data.items():
        if isinstance(value, list):  # Obsługuje listy
            fields[key] = {"arrayValue": {"values": [{"stringValue": str(item)} for item in value]}}
        elif isinstance(value, bool):  # Obsługuje wartości logiczne
            fields[key] = {"booleanValue": value}
        elif isinstance(value, int):  # Obsługuje liczby całkowite
            fields[key] = {"integerValue": str(value)}
        elif isinstance(value, datetime):  # Obsługuje wartości typu timestamp
            fields[key] = {"timestampValue": value.isoformat()}  # Firestore expects ISO 8601 format
        else:  # Obsługuje pojedyncze wartości jako stringi
            fields[key] = {"stringValue": str(value)}
    
    creation_time = datetime.now(timezone.utc)  # Pobierz aktualny czas
    fields['created_at'] = {"timestampValue": {"seconds": int(creation_time.timestamp()), "nanos": (creation_time.microsecond * 1000)}}

    # Wysyłanie danych do Firestore
    async with session.patch(url, json={"fields": fields}) as response:
        if response.status == 200:
            log_success(f"Pomyślnie zapisano użytkownika {sub_id} w kolekcji {collection}.")
        else:
            log_error(f"Błąd zapisu użytkownika: {await response.text()}")

async def update_user_data(session: ClientSession, user_id: str, sub_id: str, data: dict, collection: str):
    """Aktualizuje dane użytkownika w odpowiedniej kolekcji Firestore.
    Jeśli pojawią się nowe pola (np. "report_count"), zostaną one dodane lub zaktualizowane.
    Dodatkowo, uzupełnia pola, które powinny być obecne w Firestore (np. permissions).

    Parametry:
        session: ClientSession - sesja HTTP do wysyłania zapytań
        user_id: str - identyfikator użytkownika (dokumentu) w Firestore
        sub_id: str - dodatkowy identyfikator (np. skrócona nazwa) używany przy logowaniu
        data: dict - słownik danych do aktualizacji
        collection: str - nazwa kolekcji w Firestore
    """
    # Uzupełnienie pól domyślnych, jeśli nie zostały przekazane
    if "report_count" not in data:
        if collection == "accounts_sm":
            data["report_count"] = 0

    if "permissions" not in data:
        if collection == "admins" or "workers":
            data["permissions"] = ["admin.*"]
        elif collection == "workers":
            data["permissions"] = ["worker.*"]

    # Inne pola, takie jak email, password, first_name, last_name, birth_date, gender, user_agent, cookies
    # powinny być zawarte w słowniku 'data', jeżeli mają być zapisane do Firestore.

    url = f"{FIRESTORE_BASE_URL}/{collection}/{user_id}?key={PRIVATE_KEY}"
    
    # Przygotowanie danych do aktualizacji w Firestore
    fields = {}
    for key, value in data.items():
        if isinstance(value, list):  # Obsługa list
            fields[key] = {"arrayValue": {"values": [{"stringValue": str(item)} for item in value]}}
        elif isinstance(value, bool):  # Obsługa wartości logicznych
            fields[key] = {"booleanValue": value}
        elif isinstance(value, int):  # Obsługa liczb całkowitych
            fields[key] = {"integerValue": str(value)}
        elif isinstance(value, datetime):  # Obsługa dat i timestampów
            fields[key] = {"timestampValue": value.isoformat()}  # Firestore oczekuje formatu ISO 8601
        else:  # Obsługa pozostałych wartości jako stringi
            fields[key] = {"stringValue": str(value)}
    
    # Dodanie pola aktualizacji
    updated_time = datetime.now(timezone.utc)
    fields['updated_at'] = {"timestampValue": {"seconds": int(updated_time.timestamp()), "nanos": updated_time.microsecond * 1000}}

    # Wysyłanie zaktualizowanych danych do Firestore za pomocą metody PATCH
    async with session.patch(url, json={"fields": fields}) as response:
        if response.status == 200:
            log_success(f"Pomyślnie zaktualizowano użytkownika {sub_id} w kolekcji {collection}.")
        else:
            log_error(f"Błąd aktualizacji użytkownika: {await response.text()}")


async def save_user_mail_data(session: ClientSession, mail: str, data: dict, collection: str):
    """Zapisuje dane użytkownika do odpowiedniej kolekcji w Firestore."""
    url = f"{FIRESTORE_BASE_URL}/{collection}/{mail}?key={PRIVATE_KEY}"
    
    # Przygotowanie danych do zapisu w Firestore
    fields = {}
    for key, value in data.items():
        if isinstance(value, list):  # Obsługuje listy
            fields[key] = {"arrayValue": {"values": [{"stringValue": str(item)} for item in value]}}
        elif isinstance(value, bool):  # Obsługuje wartości logiczne
            fields[key] = {"booleanValue": value}
        elif isinstance(value, int):  # Obsługuje liczby całkowite
            fields[key] = {"integerValue": str(value)}
        elif isinstance(value, datetime):  # Obsługuje wartości typu timestamp
            fields[key] = {"timestampValue": value.isoformat()}  # Firestore expects ISO 8601 format
        else:  # Obsługuje pojedyncze wartości jako stringi
            fields[key] = {"stringValue": str(value)}

    creation_time = datetime.now(timezone.utc)  # Pobierz aktualny czas
    fields['created_at'] = {"timestampValue": {"seconds": int(creation_time.timestamp()), "nanos": (creation_time.microsecond * 1000)}}

    # Wysyłanie danych do Firestore
    async with session.patch(url, json={"fields": fields}) as response:
        if response.status == 200:
            log_success(f"Pomyślnie zapisano użytkownika {mail} w kolekcji {collection}.")
        else:
            log_error(f"Błąd zapisu użytkownika: {await response.text()}")

async def update_user_version(session: ClientSession, collection: str, user_id: str, app_version: str):
    """Aktualizuje specyfikację sprzętu i wersję aplikacji w dokumencie użytkownika."""
    url = f"{FIRESTORE_BASE_URL}/{collection}/{user_id}?key={PRIVATE_KEY}"
    update_data = {
        "fields": {
            "app_version": {"stringValue": app_version}
        }
    }
    try:
        async with session.patch(url, json=update_data) as response:
            if response.status == 200:
                log_success(f"Zaktualizowano specyfikację i wersję aplikacji dla użytkownika {user_id} w kolekcji {collection}.")
            else:
                log_error(f"Błąd aktualizacji specyfikacji i wersji dla użytkownika {user_id}: {response.status}")
    except ClientError as e:
        log_error(f"Błąd połączenia przy aktualizacji specyfikacji i wersji: {str(e)}")


async def verify_user_data(session: ClientSession, user_id: str, user_ip: str, default_account_data: Dict) -> str:
    """Sprawdza, czy użytkownik istnieje w jednej z kolekcji (admins, workers) i zwraca typ konta ('admin', 'worker') lub None.
       Jeśli brakuje wymaganych pól, uzupełnia je w Firebase."""

    async def check_user_in_collection(collection: str) -> bool:
        url = f"{FIRESTORE_BASE_URL}/{collection}/{user_id}?key={PRIVATE_KEY}"

        try:
            async with session.get(url) as response:
                if response.status == 200:
                    document = await response.json()

                    # Sprawdzamy, czy specyfikacja sprzętu i inne wymagane pola istnieją
                    if 'spec' in document['fields']:
                        stored_spec = document['fields']['spec'].get('stringValue')
                        current_spec = get_hardware_info()  # Pobieramy aktualną specyfikację sprzętu

                        # Sprawdzamy wersję aplikacji
                        stored_version = document['fields'].get('app_version', {}).get('stringValue')
                        if stored_version != LOCAL_VERSION:
                            # Jeśli wersja się różni, nadpisujemy specyfikację i zapisujemy nową wersję
                            await update_user_version(session, collection, user_id, LOCAL_VERSION)

                        if stored_spec == current_spec:
                            sub_id = document['fields'].get('sub_id', {}).get('stringValue')
                            log_success(f"Zweryfikowano użytkownika {sub_id} w kolekcji {collection} poprawnie.")
                            
                            # Sprawdzamy, czy IP jest już na liście
                            if 'ips' in document['fields']:
                                ips = document['fields']['ips']['arrayValue']['values']
                                existing_ips = [ip['stringValue'] for ip in ips]
                                if user_ip not in existing_ips:
                                    await add_ip_to_document(session, collection, user_id, user_ip)  # Dodajemy IP do listy
                            return True
                        else:
                            log_info(f"Nie udało się zweryfikować użytkownika {sub_id} w kolekcji {collection}.")
                            return False
                    else:
                        log_info(f"Nie udało się zweryfikować użytkownika w kolekcji {collection}. Brak specyfikacji sprzętu.")
                        return False

                elif response.status == 404:
                    return False
                else:
                    log_error(f"Błąd podczas sprawdzania użytkownika w kolekcji {collection}: {response.status} - {await response.text()}")
                    return False
        except ClientError as e:
            log_error(f"Błąd połączenia z Firestore w kolekcji {collection}: {str(e)}")
            return False

    # Sprawdzamy użytkownika najpierw w kolekcji 'admins', potem w 'workers'
    if await check_user_in_collection("admins"):
        # Dodaj brakujące dane, jeśli istnieją
        await add_missing_fields_to_user(session, "admins", user_id, default_account_data)
        return "admin"
    elif await check_user_in_collection("workers"):
        # Dodaj brakujące dane, jeśli istnieją
        await add_missing_fields_to_user(session, "workers", user_id, default_account_data)
        return "worker"
    else:
        return None


async def get_user_permissions(session: ClientSession, collection: str, user_id: str) -> list:
    """
    Pobiera uprawnienia użytkownika z dokumentu Firestore.
    
    :param session: Instancja aiohttp.ClientSession do wykonywania zapytań HTTP.
    :param collection: Nazwa kolekcji, np. "admins" lub "workers".
    :param user_id: Unikalny identyfikator użytkownika (ID dokumentu w Firestore).
    :return: Lista uprawnień użytkownika lub pustą listę w przypadku błędu.
    """
    url = f"{FIRESTORE_BASE_URL}/{collection}/{user_id}?key={PRIVATE_KEY}"
    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                fields = data.get("fields", {})
                permissions_field = fields.get("permissions", {})
                # Oczekujemy formatu: {"arrayValue": {"values": [{"stringValue": "admin.*"}, ...]}}
                values = permissions_field.get("arrayValue", {}).get("values", [])
                permissions = [item.get("stringValue") for item in values if "stringValue" in item]
                log_info(f"Uprawnienia użytkownika {user_id} pobrane poprawnie: {permissions}")
                return permissions
            else:
                error_text = await response.text()
                log_error(f"Nie udało się pobrać uprawnień użytkownika {user_id}: {response.status} - {error_text}")
                return []
    except Exception as e:
        log_error(f"Błąd podczas pobierania uprawnień użytkownika {user_id}: {str(e)}")
        return []


async def add_missing_fields_to_user(session: ClientSession, collection: str, user_id: str, default_account_data: Dict) -> None:
    """Sprawdza brakujące pola i uzupełnia je w Firestore dla danego użytkownika."""

    url = f"{FIRESTORE_BASE_URL}/{collection}/{user_id}?key={PRIVATE_KEY}"
    
    try:
        # Pobranie aktualnych danych użytkownika
        async with session.get(url) as response:
            if response.status == 200:
                document = await response.json()

                # Pobieramy istniejące pola użytkownika
                existing_fields = document.get('fields', {})

                # Inicjalizujemy słownik z brakującymi polami
                updated_fields = {}
                
                # Sprawdzamy brakujące pola i dodajemy je
                if 'sub_id' not in existing_fields:
                    updated_fields['sub_id'] = {"stringValue": default_account_data["sub_id"]}
                if 'ips' not in existing_fields:
                    updated_fields['ips'] = {"arrayValue": {"values": [{"stringValue": ip} for ip in default_account_data["ips"]]}}
                if 'spec' not in existing_fields:
                    updated_fields['spec'] = {"stringValue": default_account_data["spec"]}
                if 'app_version' not in existing_fields:
                    updated_fields['app_version'] = {"stringValue": default_account_data["app_version"]}
                if 'active' not in existing_fields:
                    updated_fields['active'] = {"booleanValue": default_account_data["active"]}

                existing_fields.update(updated_fields)

                if updated_fields:
                    # Wysłanie zaktualizowanych danych
                    update_url = f"{FIRESTORE_BASE_URL}/{collection}/{user_id}?key={PRIVATE_KEY}"
                    async with session.patch(update_url, json={"fields": existing_fields}) as update_response:
                        if update_response.status == 200:
                            log_success(f"Zaktualizowano brakujące pola dla użytkownika {user_id} w kolekcji {collection}.")
                        else:
                            log_error(f"Błąd podczas aktualizowania pól użytkownika {user_id} w kolekcji {collection}: {update_response.status}")
            else:
                log_error(f"Błąd pobierania danych użytkownika {user_id} z kolekcji {collection}: {response.status}")
    except ClientError as e:
        log_error(f"Błąd połączenia z Firestore podczas sprawdzania pól dla użytkownika {user_id}: {str(e)}")

async def add_ip_to_document(session, collection, user_id, user_ip):
    """Dodaje IP użytkownika do listy 'ips' w dokumencie Firestore bez usuwania obecnych danych."""
    url = f"{FIRESTORE_BASE_URL}/{collection}/{user_id}?key={PRIVATE_KEY}"

    try:
        # Pobierz aktualny dokument
        async with session.get(url) as response:
            if response.status == 200:
                document = await response.json()
                fields = document.get('fields', {})
                ips_field = fields.get('ips', {})
                ips_values = ips_field.get('arrayValue', {}).get('values', [])
                
                # Sprawdź, czy user_ip już istnieje
                existing_ips = [ip.get('stringValue') for ip in ips_values]
                if user_ip in existing_ips:
                    log_info(f"IP {user_ip} już istnieje w dokumencie użytkownika {user_id}.")
                    return
                
                # Dodaj nowy IP do listy
                existing_ips.append(user_ip)
                
                # Przygotuj dane do aktualizacji
                update_data = {
                    "fields": {
                        "ips": {
                            "arrayValue": {
                                "values": [{"stringValue": ip} for ip in existing_ips]
                            }
                        }
                    }
                }

                # Wykonaj żądanie PATCH
                async with session.patch(
                    url,
                    json=update_data,
                    params={"updateMask.fieldPaths": "ips"}  # Aktualizuje tylko pole 'ips'
                ) as update_response:
                    if update_response.status == 200:
                        log_success(f"IP {user_ip} zostało dodane do dokumentu użytkownika {user_id}.")
                    else:
                        log_error(f"Błąd podczas aktualizacji dokumentu {user_id}: {update_response.status} - {await update_response.text()}")
            else:
                log_error(f"Błąd podczas pobierania dokumentu {user_id}: {response.status} - {await response.text()}")
    except aiohttp.ClientError as e:
        log_error(f"Błąd połączenia z Firestore podczas aktualizacji IP użytkownika {user_id}: {str(e)}")

class TaskMonitor:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.session = None
        self.is_task_running = False

    async def start(self):
        """Uruchamia monitorowanie zadań."""
        self.session = ClientSession()
        try:
            while True:
                if self.is_task_running:
                    return
                await self.monitor_tasks()
                #log_info("Sprawdzono, czy są nowe zadania.")
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            pass
        finally:
            await self.close()

    async def fetch_tasks(self):
        """Pobiera zadania przypisane do user_id lub 'all', które nie zostały ukończone ani anulowane."""
        url = f"{FIRESTORE_BASE_URL}/tasks"
        
        try:
            async with self.session.get(url) as response:
                if self.is_task_running:
                    return

                response.raise_for_status()
                data = await response.json()

                tasks = data.get("documents", [])
                filtered_tasks = []

                for task in tasks:
                    fields = task.get("fields", {})

                    # Pobranie przypisanych użytkowników
                    assigned_ids = fields.get("assigned_ids", {}).get("arrayValue", {}).get("values", [])
                    assigned_users = {item.get("stringValue") for item in assigned_ids}

                    # Pobranie ukończonych użytkowników
                    completed_ids = fields.get("completed_ids", {}).get("arrayValue", {}).get("values", [])
                    completed_users = {item.get("stringValue") for item in completed_ids}
                    
                    # Pobranie anulowanych użytkowników
                    cancelled_ids = fields.get("cancelled_ids", {}).get("arrayValue", {}).get("values", [])
                    cancelled_users = {item.get("stringValue") for item in cancelled_ids}

                    # Sprawdzenie, czy użytkownik jest przypisany i nie ukończył oraz nie anulował zadania
                    if (self.user_id in assigned_users or "all" in assigned_users) and \
                    self.user_id not in completed_users and \
                    self.user_id not in cancelled_users:
                        filtered_tasks.append(task)

                return filtered_tasks

        except ClientError as e:
            log_error(f"Błąd pobierania zadań: {str(e)}")
            return []

    async def monitor_tasks(self):
        """Monitoruje i wykonuje nowe zadania."""
        if self.is_task_running:
            return

        tasks = await self.fetch_tasks()
        for task in tasks:
            task_id = task.get("name", "").split("/")[-1]  # Pobranie ID zadania
            await self.execute_task(task_id, task)

    async def execute_task(self, task_id: str, task_data: dict):
        """Wykonuje zadanie na podstawie jego typu i daty."""
        if self.is_task_running:
            return
        
        try:
            fields = task_data.get("fields", {})
            task_type = fields.get("type", {}).get("stringValue")
            date = fields.get("date", {}).get("timestampValue")
            special_attributes = {
                key: value.get("stringValue")
                for key, value in fields.items()
                if key not in {"type", "assigned_ids", "date", "assigned_by_id", "assigned_by_ip", "assigned_at", "completed_ids", "cancelled_ids"}
            }

            if date:
                task_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
                current_date = datetime.now(timezone.utc)
                if task_date > current_date:
                    return
                if current_date - task_date > timedelta(minutes=5):
                    return

            completed_ids = fields.get("completed_ids", {}).get("arrayValue", {}).get("values", [])
            completed_users = {item.get("stringValue") for item in completed_ids}
                    
            cancelled_ids = fields.get("cancelled_ids", {}).get("arrayValue", {}).get("values", [])
            cancelled_users = {item.get("stringValue") for item in cancelled_ids}

            if self.user_id in completed_users or self.user_id in cancelled_users:
                return
            
            if self.is_task_running:
                return

            clear_console()
            log_info(f"Rozpoczęto wykonywanie zadania '{task_id}' - Typ: {task_type}.")
            self.is_task_running = True

            try:
                task_type_enum = TaskType(task_type.replace("TaskType.", ""))
                handler = TASK_TYPE_HANDLERS.get(task_type_enum)

                if handler:
                    # Załóżmy, że gdy handler zwróci False, oznacza to anulowanie zadania.
                    result = await handler(task_id, self.user_id, **special_attributes) if task_type_enum != TaskType.CHECK_FOR_UPDATES else await handler(LOCAL_VERSION)
                    if result is True:
                        await self.mark_task_completed(task_id, self.user_id)
                    if result is False:
                        log_info(f"Wystąpił niezidentyfikowany błąd podczas wykonywania zadania '{task_id}'.")
                        await self.update_cancelled_list(task_id, self.user_id)
                    else:
                        log_info(f"Wystąpił niezidentyfikowany błąd podczas wykonywania zadania '{task_id}'.")
                else:
                    log_error(f"Brak obsługi dla typu zadania: {task_type_enum.name}.")
            except (ValueError, KeyError) as e:
                log_error(f"Nieprawidłowy typ zadania: {task_type} - Błąd: {str(e)}")
        finally:
            self.is_task_running = False

    async def update_user_list(self, task_id: str, new_user_id: str):
        """
        Dodaje nowe user_id do listy completed_ids w dokumencie zadania w Firestore.
        """
        url = f"{FIRESTORE_BASE_URL}/tasks/{task_id}"
        
        try:
            # Pobranie aktualnych danych dokumentu
            async with self.session.get(url) as response:
                if response.status != 200:
                    log_error(f"Błąd pobierania dokumentu {task_id}: {response.status} - {await response.text()}")
                    return

                document_data = await response.json()
                existing_fields = document_data.get("fields", {})
                completed_ids_field = existing_fields.get("completed_ids", {}).get("arrayValue", {}).get("values", [])
                existing_users = [item.get("stringValue") for item in completed_ids_field]

            # Dodanie nowego użytkownika do listy, jeśli go tam nie ma
            if new_user_id not in existing_users:
                existing_users.append(new_user_id)

            # Przygotowanie danych do aktualizacji
            update_data = {
                "fields": {
                    "completed_ids": {
                        "arrayValue": {"values": [{"stringValue": user} for user in existing_users]}
                    }
                }
            }

            # Użycie updateMask, aby aktualizować tylko `completed_ids`
            params = {"updateMask.fieldPaths": "completed_ids"}
            
            async with self.session.patch(url, json=update_data, params=params) as update_response:
                if update_response.status in {200, 204}:
                    log_success(f"Lista użytkowników dla zadania {task_id} została zaktualizowana.")
                else:
                    log_error(f"Błąd aktualizacji listy użytkowników: {update_response.status} - {await update_response.text()}")

        except Exception as e:
            log_error(f"Błąd podczas aktualizacji listy użytkowników: {str(e)}")

    async def update_cancelled_list(self, task_id: str, user_id: str):
        """
        Dodaje id użytkownika do listy cancelled_ids w dokumencie zadania.
        """
        url = f"{FIRESTORE_BASE_URL}/tasks/{task_id}"
        try:
            # Pobranie aktualnych danych dokumentu
            async with self.session.get(url) as response:
                if response.status != 200:
                    log_error(f"Błąd pobierania dokumentu {task_id} podczas anulowania: {response.status} - {await response.text()}")
                    return
                document_data = await response.json()
                existing_fields = document_data.get("fields", {})
                cancelled_field = existing_fields.get("cancelled_ids", {}).get("arrayValue", {}).get("values", [])
                existing_ids = [item.get("stringValue") for item in cancelled_field]
            
            # Dodaj user_id, jeśli go tam jeszcze nie ma
            if user_id not in existing_ids:
                existing_ids.append(user_id)
            
            update_data = {
                "fields": {
                    "cancelled_ids": {
                        "arrayValue": {"values": [{"stringValue": uid} for uid in existing_ids]}
                    }
                }
            }
            params = {"updateMask.fieldPaths": "cancelled_ids"}
            async with self.session.patch(url, json=update_data, params=params) as patch_response:
                if patch_response.status in {200, 204}:
                    log_success(f"Zaktualizowano cancelled_ids dla zadania {task_id}.")
                else:
                    log_error(f"Błąd aktualizacji cancelled_ids: {patch_response.status} - {await patch_response.text()}")
        except Exception as e:
            log_error(f"Błąd podczas aktualizacji cancelled_ids: {e}")


    async def mark_task_completed(self, task_id: str, user_id: str):
        """
        Oznacza zadanie jako ukończone i aktualizuje listę assigned_ids.
        """
        try:
            await self.update_user_list(task_id, user_id)
        except ClientError as e:
            log_error(f"Błąd oznaczania zadania {task_id} jako ukończone: {str(e)}")

    async def close(self):
        """Zamyka sesję."""
        if self.session:
            await self.session.close()