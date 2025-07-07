import os
import json
import asyncio
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import traceback

import aiohttp
from aiohttp import ClientSession, ClientError, ClientTimeout

from utils.utils import log_error, log_info, log_success, get_hardware_info, clear_console
from core.config_manager import LOCAL_VERSION
from utils.banks import AccountType
from network.updater import check_for_updates
from automation.social_media import TikTok
from automation.email_account import Google
from utils.tasks import TaskType

# -------------------------------
# Konfiguracja i stałe
# -------------------------------

FIREBASE_ADMIN_KEY_PATH = os.getenv("FIREBASE_ADMIN_KEY_PATH")
with open(FIREBASE_ADMIN_KEY_PATH, 'r') as key_file:
    admin_key = json.load(key_file)

API_KEY = admin_key["api_key"]
PROJECT_ID = admin_key["project_id"]
FIRESTORE_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

TASK_TYPE_HANDLERS = {
    TaskType.CHECK_FOR_UPDATES: check_for_updates,
    TaskType.TT_COPY_ACCOUNT_DATA: TikTok().copy_accounts,
    TaskType.TT_MASS_REPORT: TikTok().mass_report,
    TaskType.G_GENERATE_ACCOUNT: Google().generate_account,
    # TaskType.GENERATE_ACCOUNT: handle_generate_account,  # zakomentowane
}

# -------------------------------
# Helpery i warstwa abstrakcyjna
# -------------------------------

def get_firestore_headers() -> Dict[str, str]:
    """
    Zwraca nagłówki HTTP wymagane do komunikacji z Firestore.
    """
    return {
        "Content-Type": "application/json",
    }

def firestore_format_value(value):
    """
    Formatuje wartość do formatu Firestore JSON API zgodnie z typem.
    """
    if isinstance(value, bool):
        return {"booleanValue": value}
    elif isinstance(value, str):
        return {"stringValue": value}
    elif isinstance(value, datetime):
        # ISO 8601 z sufiksem Z (UTC)
        iso = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return {"timestampValue": iso}
    else:
        # Domyślnie string, można rozbudować o inne typy (int, float etc.)
        return {"stringValue": str(value)}

def format_firestore_data(data: Dict[str, object]) -> Dict[str, Dict]:
    """
    Formatuje słownik Python do formatu JSON zgodnego z Firestore API.
    """
    return {key: firestore_format_value(value) for key, value in data.items()}

# -------------------------------
# Klasa klienta Firestore (dla testowalności)
# -------------------------------

class FirestoreClient:
    """
    Abstrakcja do komunikacji z Firestore przez REST API.
    Umożliwia mockowanie w testach.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 10.0
    ):
        self.api_key = api_key or API_KEY
        self.base_url = base_url or FIRESTORE_BASE_URL
        self.timeout = timeout
        self.session: Optional[ClientSession] = None

    async def __aenter__(self):
        timeout = ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    def _build_url(self, collection: str, doc_id: Optional[str] = None) -> str:
        url = f"{self.base_url}/{collection}"
        if doc_id:
            url += f"/{doc_id}"
        full_url = f"{url}?key={self.api_key}"
        #log_info(f"DEBUG URL: {full_url}")
        return full_url


    async def get(self, collection: str, doc_id: Optional[str] = None) -> Optional[Dict]:
        """
        Pobiera dokument lub kolekcję.
        """
        url = self._build_url(collection, doc_id)
        try:
            async with self.session.get(url, headers=get_firestore_headers()) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    return None
                else:
                    text = await resp.text()
                    # Tu dodajemy stacktrace do wyjątku
                    stack = traceback.format_stack()
                    raise ClientError(f"GET {url} - status: {resp.status}, response: {text}\nStack trace:\n{''.join(stack)}")
        except Exception as e:
            # Możemy też dopisać stacktrace jeśli wyjątek nie pochodzi z powyższego
            stack = traceback.format_exc()
            raise ClientError(f"GET {url} - błąd: {e}\nStack trace:\n{stack}") from e

    async def patch(self, collection: str, doc_id: str, data: Dict, update_mask_fields: Optional[List[str]] = None) -> None:
        """
        Aktualizuje dokument w Firestore.
        """
        url = self._build_url(collection, doc_id)
        params = {}
        if update_mask_fields:
            params["updateMask.fieldPaths"] = ",".join(update_mask_fields)
        try:
            async with self.session.patch(
                url, json={"fields": data}, headers=get_firestore_headers(), params=params
            ) as resp:
                if resp.status not in {200, 201}:
                    text = await resp.text()
                    stack = traceback.format_stack()
                    raise ClientError(f"PATCH {url} - status: {resp.status}, response: {text}\nStack trace:\n{''.join(stack)}")
        except Exception as e:
            stack = traceback.format_exc()
            raise ClientError(f"PATCH {url} - błąd: {e}\nStack trace:\n{stack}") from e

# -------------------------------
# Operacje na dokumentach Firestore
# -------------------------------

async def check_connection(client: FirestoreClient) -> None:
    """
    Sprawdza połączenie z Firestore.
    """
    try:
        data = await with_retry(lambda: client.get("users"))
        if data is not None:
            log_info("Połączenie z Firestore działa poprawnie.")
        else:
            log_error("Połączenie działa, ale kolekcja 'users' nie istnieje.")
    except Exception as e:
        stack = traceback.format_exc()
        log_error(f"Błąd połączenia z Firestore: {e}, Traceback: {stack}")

async def document_exists(client: FirestoreClient, collection: str, doc_id: str) -> bool:
    """
    Sprawdza, czy dokument istnieje.
    """
    try:
        doc = await with_retry(client.get, collection=collection, doc_id=doc_id)
        return doc is not None
    except Exception as e:
        log_error(f"Błąd sprawdzania istnienia dokumentu '{doc_id}' w '{collection}': {e}")
        return False

async def create_or_update_document(client: FirestoreClient, collection: str, doc_id: str, data: Dict[str, object]) -> None:
    """
    Tworzy lub aktualizuje dokument w Firestore.
    Jeśli dokument istnieje, aktualizuje pole 'active' na True.
    """
    try:
        if await document_exists(client, collection, doc_id):
            # Aktualizacja pola active na True
            update_data = format_firestore_data({"active": True})
            await with_retry(client.patch, collection, doc_id, update_data, update_mask_fields=["active"])
            log_info(f"Dokument '{doc_id}' w kolekcji '{collection}' został zaktualizowany.")
        else:
            # Tworzymy nowy dokument z danymi
            formatted_data = format_firestore_data(data)
            await with_retry(client.patch, collection, doc_id, formatted_data)
            log_info(f"Dokument '{doc_id}' w kolekcji '{collection}' został zapisany.")
    except Exception as e:
        log_error(f"Błąd podczas tworzenia/aktualizacji dokumentu '{doc_id}': {e}")

async def fetch_active_workers(client: FirestoreClient) -> List[Dict]:
    """
    Pobiera wszystkich aktywnych pracowników (active == True) z kolekcji 'workers'.
    """
    try:
        data = await with_retry(client.get, collection="workers")
        if not data:
            return []

        workers = data.get("documents", [])
        active_workers = []
        for worker in workers:
            fields = worker.get("fields", {})
            is_active = fields.get("active", {}).get("booleanValue", False)
            if is_active:
                active_workers.append(worker)

        return active_workers
    except Exception as e:
        log_error(f"Błąd podczas pobierania aktywnych pracowników: {e}")
        return []

async def set_account_state(
    client: FirestoreClient,
    user_id: str,
    account_type: Optional[AccountType],
    is_active: bool
) -> None:
    """
    Ustawia stan aktywności konta w Firestore.
    Jeśli account_type jest None, sprawdza kolekcje ADMIN i WORKER.
    """
    collections = [account_type.value] if account_type else [AccountType.ADMIN.value, AccountType.WORKER.value]
    update_data = format_firestore_data({"active": is_active})
    update_fields = ["active"]

    for collection in collections:
        try:
            doc = await with_retry(client.get, collection=collection, doc_id=user_id)
            if doc is None:
                # Dokument nie istnieje w tej kolekcji - sprawdź następną
                continue

            current_active = doc.get("fields", {}).get("active", {}).get("booleanValue", None)
            if current_active == is_active:
                log_info(f"Konto '{user_id}' w kolekcji '{collection}' już ma active={is_active}. Aktualizacja pominięta.")
                return

            await with_retry(client.patch, collection, user_id, update_data, update_mask_fields=update_fields)
            state_str = "aktywne" if is_active else "nieaktywne"
            log_info(f"Konto '{user_id}' w kolekcji '{collection}' oznaczone jako {state_str}.")
            return

        except Exception as e:
            log_error(f"Błąd podczas ustawiania stanu konta '{user_id}' w '{collection}': {e}")
            return

    log_error(f"Nie znaleziono użytkownika '{user_id}' w kolekcjach: {', '.join(collections)}.")

async def run_worker_loop():
    """
    Przykładowa pętla wykonywania zadań na aktywnych pracownikach.
    """
    async with FirestoreClient(API_KEY, FIRESTORE_BASE_URL) as client:
        while True:
            active_workers = await fetch_active_workers(client)

            for worker_doc in active_workers:
                # Wyciągnięcie user_id z dokumentu
                name_path = worker_doc.get("name", "")
                user_id = name_path.split("/")[-1] if name_path else None

                if not user_id:
                    log_error("Nie można wyciągnąć user_id z dokumentu.")
                    continue

                task_type_str = worker_doc.get("fields", {}).get("task_type", {}).get("stringValue")
                if not task_type_str:
                    log_error(f"Brak task_type dla worker {user_id}")
                    continue

                task_func = TASK_TYPE_HANDLERS.get(TaskType(task_type_str))
                if task_func is None:
                    log_error(f"Nieznany typ zadania: {task_type_str}")
                    continue

                log_info(f"Uruchamiam zadanie {task_type_str} dla {user_id}")
                try:
                    await task_func()
                    log_success(f"Zadanie {task_type_str} dla {user_id} zakończone sukcesem.")
                except Exception as e:
                    log_error(f"Błąd podczas wykonywania zadania {task_type_str} dla {user_id}: {e}")

            await asyncio.sleep(10)  # Przerwa między kolejnymi pętlami

# -------------------------------
# Helpery i warstwa abstrakcji
# -------------------------------

def get_headers() -> Dict[str, str]:
    """
    Zwraca nagłówki HTTP wymagane przez Firestore REST API.
    """
    return {"Content-Type": "application/json"}

def iso8601_utc(dt: Optional[datetime] = None) -> str:
    """
    Konwertuje datetime na string ISO 8601 z sufiksem Z (UTC).
    """
    dt = dt or datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def format_value(value):
    """
    Formatuje Python-ową wartość na strukturę Firestore JSON API.
    """
    if isinstance(value, bool):
        return {"booleanValue": value}
    elif isinstance(value, str):
        return {"stringValue": value}
    elif isinstance(value, datetime):
        return {"timestampValue": iso8601_utc(value)}
    elif isinstance(value, list):
        return {"arrayValue": {"values": [format_value(v) for v in value]}}
    else:
        # domyślnie zamieniamy na string
        return {"stringValue": str(value)}

async def with_retry(func, *args, retries=3, delay=1, **kwargs):
    for attempt in range(1, retries + 1):
        try:
            result = await func(*args, **kwargs)  # <-- await tutaj
            log_success(f"[Próba {attempt}/{retries}] success")
            return result
        except Exception as e:
            log_error(f"[Próba {attempt}/{retries}] {e}")
            if attempt == retries:
                raise
            await asyncio.sleep(delay)

# -------------------------------
# Funkcje pomocnicze
# -------------------------------

async def cleanup_loop(user_id: str, account_type: AccountType):
    """
    Wywoływane przy zamykaniu aplikacji z pętlą asyncio.
    Zatrzymuje loop i asynchronicznie ustawia konto jako nieaktywne.
    """
    try:
        asyncio.get_running_loop().stop()
    except RuntimeError:
        pass
    await cleanup(user_id, account_type)

async def cleanup(user_id: str, account_type: AccountType):
    """
    Asynchronicznie oznacza konto jako nieaktywne w Firestore.
    """
    try:
        async with FirestoreClient(API_KEY, FIRESTORE_BASE_URL) as client:
            await with_retry(client.patch,
                             "workers" if account_type == AccountType.WORKER else "admins",
                             user_id,
                             {"active": {"booleanValue": False}},
                             mask=["active"])
    except Exception as e:
        log_error(f"Cleanup error: {e}")

async def create_task(
    client: FirestoreClient,
    task_type: TaskType,
    assigned_ids: List[str],
    date: Optional[str] = None,
    assigned_by_id: Optional[str] = None,
    assigned_by_ip: Optional[str] = None,
    special_attributes: Optional[Dict[str, str]] = None
):
    """
    Tworzy nowy dokument zadania w kolekcji 'tasks'.
    Numeruje je automatycznie, obsługuje timestampy i dodatkowe atrybuty.
    """
    if not assigned_ids:
        log_error("Pole 'assigned_ids' jest wymagane.")
        return

    # pobierz istniejace tasks i wyznacz kolejną nazwę
    existing = await with_retry(client.get, "tasks")
    next_num = determine_next_task_number(existing or [])
    doc_name = f"task{next_num}"

    now = datetime.now(timezone.utc)
    assigned_ts = {"seconds": int(now.timestamp()), "nanos": now.microsecond * 1000}

    # buduj pola dokumentu
    fields = {
        "type": format_value(f"TaskType.{task_type.value}"),
        "assigned_ids": format_value(assigned_ids),
        "completed_ids": format_value([]),
        "cancelled_ids": format_value([]),
        "assigned_by_id": format_value(assigned_by_id or ""),
        "assigned_by_ip": format_value(assigned_by_ip or ""),
        "assigned_at": {"timestampValue": assigned_ts},
    }

    # data parametryczna
    if date:
        try:
            dt = datetime.fromisoformat(date)
            ts = {"seconds": int(dt.timestamp()), "nanos": dt.microsecond * 1000}
            fields["date"] = {"timestampValue": ts}
        except Exception:
            log_error(f"Niepoprawny format daty: {date}")
            fields["date"] = {"timestampValue": assigned_ts}
    else:
        fields["date"] = {"timestampValue": assigned_ts}

    # dodatkowe atrybuty
    if special_attributes:
        for k, v in special_attributes.items():
            fields[k] = format_value(str(v))

    # wykonaj zapis
    try:
        await with_retry(client.patch, "tasks", doc_name, fields)
        log_success(f"Utworzono zadanie {doc_name}.")
    except Exception as e:
        log_error(f"Błąd tworzenia zadania: {e}")

async def fetch_existing_tasks(client: FirestoreClient) -> List[dict]:
    """
    Pobiera wszystkie dokumenty z kolekcji 'tasks'.
    """
    try:
        result = await with_retry(client.get, "tasks")
        return result.get("documents", []) if result else []
    except Exception as e:
        log_error(f"Błąd pobierania zadań: {e}")
        return []

def determine_next_task_number(existing: List[dict]) -> int:
    """
    Analizuje nazwy dokumentów (taskX) i zwraca kolejny numer.
    """
    nums = []
    for doc in existing:
        name = doc.get("name", "").split("/")[-1]
        if name.startswith("task") and name[4:].isdigit():
            nums.append(int(name[4:]))
    return max(nums, default=0) + 1

async def get_active_workers(client: FirestoreClient) -> List[Dict[str, str]]:
    """
    Zwraca listę aktywnych pracowników z kolekcji 'workers'.
    Każdy element to dict z sub_id i id dokumentu.
    """
    try:
        data = await with_retry(client.get, "workers")
        docs = data.get("documents", []) if data else []
        result = []
        for doc in docs:
            f = doc.get("fields", {})
            if f.get("active", {}).get("booleanValue", False):
                sub = f.get("sub_id", {}).get("stringValue")
                uid = doc.get("name", "").split("/")[-1]
                if sub:
                    result.append({"sub_id": sub, "id": uid})
        return result
    except Exception as e:
        log_error(f"Błąd pobierania aktywnych workers: {e}")
        return []
async def check_document_exists(
    client: FirestoreClient,
    user_id: str,
    collection: str
) -> bool:
    """
    Sprawdza, czy dokument o danym user_id istnieje w kolekcji.
    """
    try:
        doc = await with_retry(client.get, collection, user_id)
        return doc is not None
    except Exception as e:
        log_error(f"check_document_exists error: {e}")
        return False

async def increment_recovery_count(
    client: FirestoreClient,
    mail: str
) -> None:
    """
    Zwiększa recovery_count w dokumencie mail_database/{prefix_of_mail}.
    """
    doc_id = mail.split("@")[0]
    try:
        # Pobranie dokumentu
        doc = await with_retry(client.get, "mail_database", doc_id)
        fields = doc.get("fields", {}) if doc else {}
        current = int(fields.get("recovery_count", {}).get("integerValue", "0"))
        new = current + 1
        # Aktualizacja
        fields["recovery_count"] = {"integerValue": str(new)}
        await with_retry(
            client.patch,
            "mail_database",
            doc_id,
            fields,
            mask=["recovery_count"]
        )
        log_success(f"recovery_count dla {mail} → {new}")
    except Exception as e:
        log_error(f"increment_recovery_count error: {e}")

async def increment_count(
    client: FirestoreClient,
    name: str,
    collection: str,
    field: str
) -> None:
    """
    Zwiększa wartość pola `field` w dokumencie collection/{name_lower}.
    """
    doc_id = name.lower()
    try:
        doc = await with_retry(client.get, collection, doc_id)
        fields = doc.get("fields", {}) if doc else {}
        current = int(fields.get(field, {}).get("integerValue", "0"))
        new = current + 1
        fields[field] = {"integerValue": str(new)}
        await with_retry(
            client.patch,
            collection,
            doc_id,
            fields,
            mask=[field]
        )
        log_success(f"{field} dla {name} → {new}")
    except Exception as e:
        log_error(f"increment_count error ({collection}/{doc_id}): {e}")

async def save_user_data(
    client: FirestoreClient,
    user_id: str,
    sub_id: str,
    data: Dict[str, Any],
    collection: str
) -> None:
    """
    Tworzy lub zapisuje dane użytkownika w collection/{user_id}.
    Uzupełnia domyślne uprawnienia i dodaje timestamp created_at.
    """
    # Domyślne permissions
    if "permissions" not in data:
        data["permissions"] = ["admin.*"] if collection == "admins" else ["worker.*"]

    # Formatowanie pól
    fields: Dict[str, Any] = {
        k: format_value(v)
        for k, v in data.items()
    }
    now = datetime.now(timezone.utc)
    fields["created_at"] = {
        "timestampValue": {
            "seconds": int(now.timestamp()),
            "nanos": now.microsecond * 1000
        }
    }

    try:
        await with_retry(client.patch, collection, user_id, fields)
        log_success(f"Saved user {sub_id} in {collection}")
    except Exception as e:
        log_error(f"save_user_data error: {e}")

async def update_user_data(
    client: FirestoreClient,
    user_id: str,
    sub_id: str,
    data: Dict[str, Any],
    collection: str
) -> None:
    """
    Aktualizuje dane użytkownika w collection/{user_id}.
    Dodaje/aktualizuje nowe pola i uzupełnia updated_at.
    """
    # Uzupełnienia domyślne
    if "report_count" not in data and collection == "accounts_sm":
        data["report_count"] = 0
    if "permissions" not in data:
        data["permissions"] = ["admin.*"] if collection == "admins" else ["worker.*"]

    # Formatowanie pól
    fields: Dict[str, Any] = {}
    for k, v in data.items():
        fields[k] = format_value(v)

    # Timestamp updated_at
    now = datetime.now(timezone.utc)
    fields["updated_at"] = {
        "timestampValue": {
            "seconds": int(now.timestamp()),
            "nanos": now.microsecond * 1000
        }
    }

    try:
        await with_retry(
            client.patch,
            collection,
            user_id,
            fields,
            mask=list(fields.keys())
        )
        log_success(f"Updated user {sub_id} in {collection}")
    except Exception as e:
        log_error(f"update_user_data error: {e}")


async def save_user_mail_data(
    client: FirestoreClient,
    mail: str,
    data: Dict[str, Any],
    collection: str
) -> None:
    """
    Zapisuje dokument mail_database/{mail} z polami z data + created_at.
    """
    # Format pól
    fields = {k: format_value(v) for k, v in data.items()}
    now = datetime.now(timezone.utc)
    fields["created_at"] = {
        "timestampValue": {
            "seconds": int(now.timestamp()),
            "nanos": now.microsecond * 1000
        }
    }
    try:
        await with_retry(client.patch, collection, mail, fields)
        log_success(f"Saved mail {mail} in {collection}")
    except Exception as e:
        log_error(f"save_user_mail_data error: {e}")

async def update_user_version(
    client: FirestoreClient,
    collection: str,
    user_id: str,
    app_version: str
) -> None:
    """
    Ustawia field app_version w document collection/{user_id}.
    """
    fields = {"app_version": {"stringValue": app_version}}
    try:
        await with_retry(client.patch, collection, user_id, fields, mask=["app_version"])
        log_success(f"Updated version for {user_id}")
    except Exception as e:
        log_error(f"update_user_version error: {e}")

async def verify_user_data(
    client: FirestoreClient,
    user_id: str,
    user_ip: str,
    default_account_data: Dict[str, Any]
) -> Optional[str]:
    """
    Weryfikuje dokument w admins lub workers, aktualizuje wersję/spec,
    dodaje brakujące pola i zwraca 'admin'/'worker' lub None.
    """
    async def check_in(col: str) -> bool:
        doc = await with_retry(client.get, col, user_id)
        if not doc:
            return False

        fields = doc.get("fields", {})
        spec = fields.get("spec", {}).get("stringValue")
        stored_v = fields.get("app_version", {}).get("stringValue")
        current_spec = get_hardware_info()

        if spec and stored_v == LOCAL_VERSION and spec == current_spec:
            # update ip list
            ips = [ip["stringValue"] for ip in fields.get("ips", {}).get("arrayValue", {}).get("values", [])]
            if user_ip not in ips:
                ips.append(user_ip)
                await with_retry(
                    client.patch,
                    col,
                    user_id,
                    {"ips": {"arrayValue": {"values": [{"stringValue": ip} for ip in ips]}}}
                )
            return True

        # if version mismatch or spec mismatch, update
        await update_user_version(client, col, user_id, LOCAL_VERSION)
        return False

    if await check_in("admins"):
        await add_missing_fields_to_user(client, "admins", user_id, default_account_data)
        return "admin"
    if await check_in("workers"):
        await add_missing_fields_to_user(client, "workers", user_id, default_account_data)
        return "worker"
    return None

async def get_user_permissions(
    client: FirestoreClient,
    collection: str,
    user_id: str
) -> List[str]:
    """
    Zwraca listę stringValue z permissions arrayValue.
    """
    try:
        doc = await with_retry(client.get, collection, user_id)
        if not doc:
            return []
        vals = doc["fields"].get("permissions", {}).get("arrayValue", {}).get("values", [])
        perms = [v["stringValue"] for v in vals if "stringValue" in v]
        log_info(f"Permissions for {user_id}: {perms}")
        return perms
    except Exception as e:
        stack = traceback.format_exc()
        log_error(f"get_user_permissions error: {e} \n {stack}")
        return []

async def add_missing_fields_to_user(
    client: FirestoreClient,
    collection: str,
    user_id: str,
    default_data: Dict[str, Any]
) -> None:
    """
    Sprawdza i dodaje brakujące pola sub_id, ips, spec, app_version, active.
    """
    try:
        doc = await with_retry(client.get, collection, user_id)
        if not doc:
            log_error(f"No document to update in {collection}/{user_id}")
            return

        fields = doc.get("fields", {})
        updates: Dict[str, Any] = {}
        # dla każdego pola: jeśli brak, dodaj z default_data
        for field in ("sub_id", "ips", "spec", "app_version", "active"):
            if field not in fields and field in default_data:
                updates[field] = format_value(default_data[field])

        if updates:
            # merge z istniejącymi
            merged = {**{k: fields[k] for k in fields}, **updates}
            await with_retry(client.patch, collection, user_id, merged)
            log_success(f"Added missing fields for {user_id}")
    except Exception as e:
        log_error(f"add_missing_fields_to_user error: {e}")
    
async def add_ip_to_document(
    client: FirestoreClient,
    collection: str,
    user_id: str,
    user_ip: str
) -> None:
    """
    Dodaje nowe IP do pola 'ips' w dokumencie Firestore collection/{user_id},
    zachowując istniejące adresy.
    """
    try:
        # 1. Pobierz dokument
        doc = await with_retry(client.get, collection, user_id)
        if not doc:
            log_error(f"Document {collection}/{user_id} not found")
            return

        # 2. Wyciągnij istniejącą listę IP
        fields = doc.get("fields", {})
        ips_vals = fields.get("ips", {}).get("arrayValue", {}).get("values", [])
        existing_ips = [item.get("stringValue") for item in ips_vals if "stringValue" in item]

        # 3. Sprawdź, czy IP już jest na liście
        if user_ip in existing_ips:
            log_info(f"IP {user_ip} already present for {user_id}")
            return

        # 4. Dodaj nowe IP
        existing_ips.append(user_ip)

        # 5. Zbuduj zaktualizowane pole 'ips'
        updated_field = {
            "ips": {
                "arrayValue": {
                    "values": [{"stringValue": ip} for ip in existing_ips]
                }
            }
        }

        # 6. Wyślij PATCH z updateMask tylko dla 'ips'
        await with_retry(
            client.patch,
            collection,
            user_id,
            updated_field,
            mask=["ips"]
        )
        log_success(f"Added IP {user_ip} to {collection}/{user_id}")
    except Exception as e:
        log_error(f"add_ip_to_document error: {e}")

class TaskMonitor:
    """
    Monitoruje dokumenty w kolekcji 'tasks' i wykonuje je, 
    aktualizując pola completed_ids lub cancelled_ids.
    """

    def __init__(self, user_id: str, client: FirestoreClient):
        self.client = client
        self.user_id = user_id
        self.is_task_running = False

    async def start(self) -> None:
        """Uruchamia pętlę monitorującą nowe zadania co 15s."""
        try:
            while True:
                if not self.is_task_running:
                    await self.check_and_execute()
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            pass

    async def check_and_execute(self) -> None:
        """Pozyskuje niewykonane zadania i uruchamia je kolejno."""
        tasks = await self.fetch_pending_tasks()
        for doc in tasks:
            task_id = doc["name"].rsplit("/", 1)[-1]
            await self.execute_task(task_id, doc["fields"])

    async def fetch_pending_tasks(self) -> List[Dict[str, Any]]:
        """
        Pobiera wszystkie zadania, filtruje te przypisane do self.user_id lub 'all',
        które nie są ukończone ani anulowane.
        """
        try:
            data = await with_retry(self.client.get, "tasks")
            docs = data.get("documents", []) if data else []
            result = []
            for d in docs:
                f = d.get("fields", {})
                assigned = {v["stringValue"] for v in f.get("assigned_ids", {}).get("arrayValue", {}).get("values", [])}
                completed = {v["stringValue"] for v in f.get("completed_ids", {}).get("arrayValue", {}).get("values", [])}
                cancelled = {v["stringValue"] for v in f.get("cancelled_ids", {}).get("arrayValue", {}).get("values", [])}
                if (self.user_id in assigned or "all" in assigned) and \
                   self.user_id not in completed and \
                   self.user_id not in cancelled:
                    result.append(d)
            return result
        except Exception as e:
            log_error(f"fetch_pending_tasks error: {e}")
            return []

    async def execute_task(self, task_id: str, fields: Dict[str, Any]) -> None:
        """
        Sprawdza datę zadania, typ, wywołuje handler i oznacza zadanie
        jako ukończone lub anulowane.
        """
        # Wczesne wyjścia
        date_str = fields.get("date", {}).get("timestampValue")
        if date_str:
            task_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if task_dt > now or now - task_dt > timedelta(minutes=5):
                return

        # pobierz typ i dodatkowe atrybuty
        raw = fields.get("type", {}).get("stringValue", "")
        try:
            t_enum = TaskType(raw.replace("TaskType.", ""))
        except ValueError:
            log_error(f"Unknown task type: {raw}")
            return

        extras = {
            k: v["stringValue"]
            for k, v in fields.items()
            if k not in {
                "type", "assigned_ids", "completed_ids", "cancelled_ids",
                "assigned_by_id", "assigned_by_ip", "assigned_at", "date"
            }
        }

        handler = TASK_TYPE_HANDLERS.get(t_enum)
        if not handler:
            log_error(f"No handler for {t_enum}")
            return

        self.is_task_running = True
        clear_console()
        log_info(f"Executing {task_id} ({t_enum.name})")
        try:
            result = await handler(task_id=task_id, user_id=self.user_id, **extras) \
                     if t_enum != TaskType.CHECK_FOR_UPDATES \
                     else await handler(version=extras.get("version"))
            if result is True:
                await self._update_list(task_id, "completed_ids")
            else:
                await self._update_list(task_id, "cancelled_ids")
        except Exception as e:
            log_error(f"execute_task error: {e}")
        finally:
            self.is_task_running = False

    async def _update_list(self, task_id: str, list_field: str) -> None:
        """
        Dodaje self.user_id do pola list_field (completed_ids lub cancelled_ids)
        w dokumencie tasks/{task_id}.
        """
        try:
            doc = await with_retry(self.client.get, "tasks", task_id)
            if not doc:
                log_error(f"Task {task_id} not found")
                return

            vals = doc["fields"].get(list_field, {}).get("arrayValue", {}).get("values", [])
            ids = [v["stringValue"] for v in vals if "stringValue" in v]
            if self.user_id not in ids:
                ids.append(self.user_id)
                fields = {list_field: {"arrayValue": {"values": [{"stringValue": uid} for uid in ids]}}}
                await with_retry(self.client.patch, "tasks", task_id, fields, mask=[list_field])
                log_success(f"{list_field} updated for {task_id}")
        except Exception as e:
            log_error(f"_update_list error ({list_field}): {e}")