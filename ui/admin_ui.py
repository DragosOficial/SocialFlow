import os
import asyncio
import time
from colorama import Fore, Style, init
from aiohttp import ClientSession
from utils.utils import clear_console, log_info, log_error, log_success
from utils import banks
from core.user_manager import UserManager
from network.firebase_client import create_task, get_active_workers, TaskType, cleanup

init(autoreset=True)

# Przykładowe logo panelu administratora
SOCIALFLOW_ASCII = """
 ██████╗ █████╗  █████╗ ██╗ █████╗ ██╗        ███████╗██╗      █████╗  ██╗       ██╗
██╔════╝██╔══██╗██╔══██╗██║██╔══██╗██║        ██╔════╝██║     ██╔══██╗ ██║  ██╗  ██║
╚█████╗ ██║  ██║██║  ╚═╝██║███████║██║        █████╗  ██║     ██║  ██║ ╚██╗████╗██╔╝
 ╚═══██╗██║  ██║██║  ██╗██║██╔══██║██║        ██╔══╝  ██║     ██║  ██║  ████╔═████║ 
██████╔╝╚█████╔╝╚█████╔╝██║██║  ██║███████╗   ██║     ███████╗╚█████╔╝  ╚██╔╝ ╚██╔╝ 
╚═════╝  ╚════╝  ╚════╝ ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝     ╚══════╝ ╚════╝    ╚═╝   ╚═╝  
"""

def error_animation(message):
    for _ in range(3):
        print(Fore.RED + message + Style.RESET_ALL, end="\r")
        time.sleep(0.3)
        print(" " * len(message), end="\r")
        time.sleep(0.3)
    print(Fore.RED + message + Style.RESET_ALL)

# --------------------------------------------------------------------------------
# Funkcja wyświetlająca menu oparte o słowniki (główne menu)
def display_menu(options, title):
    clear_console()
    print(Fore.LIGHTMAGENTA_EX + SOCIALFLOW_ASCII + Style.RESET_ALL)
    print(Fore.LIGHTBLUE_EX + f"\n============ {title.upper()} ============" + Style.RESET_ALL)
    for index, option in enumerate(options, start=1):
        # Używamy Fore.RED dla ostatniej opcji, a Fore.YELLOW dla pozostałych
        num_color = Fore.RED if index == len(options) else Fore.YELLOW
        print(f" {num_color}{index}.{Style.RESET_ALL} {Fore.LIGHTGREEN_EX}{option['text']}")
    print(Fore.LIGHTBLUE_EX + "=" * (len(title) + 22) + Style.RESET_ALL)

# --------------------------------------------------------------------------------
# Nowa zakładka: Bank Social Media – wybór odpowiedniego banku
# Nowa wersja menu wyboru banku Social Media oparta o słowniki z uprawnieniami
async def social_media_bank_menu(user_manager: UserManager):
    if not user_manager.has_permission("admin.social_media"):
        log_error("Brak uprawnień do banku Social Media.")
        await asyncio.sleep(2)
        return

    options = [
        {
            "text": "TikTok", 
            "permission": "admin.social_media.tiktok", 
            "func": lambda um: social_media_account_manager(0, um)
        }]
    if user_manager.has_permission("dec.social_media"):
        options.append(
        {
            "text": "Instagram", 
            "permission": "dev.social_media.instagram", 
            "func": lambda um: social_media_account_manager(1, um)
        },
        {
            "text": "X", 
            "permission": "dev.social_media.x", 
            "func": lambda um: social_media_account_manager(2, um)
        },
        {
            "text": "YouTube", 
            "permission": "dev.social_media.youtube", 
            "func": lambda um: social_media_account_manager(3, um)
        })
    options.append({"text": "Powrót", "permission": None, "func": None})

    while True:
        display_menu(options, "Wybierz Bank")
        choice = input(Fore.CYAN + "\nWybierz opcję (1-5): " + Style.RESET_ALL).strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if idx < 0 or idx >= len(options):
                log_error("Nieprawidłowy wybór.")
                continue
            selected = options[idx]
            if selected["text"] == "Powrót":
                break
            perm = selected.get("permission")
            if perm and not user_manager.has_permission(perm):
                log_error("Brak uprawnień do tej opcji.")
                await asyncio.sleep(1)
                continue
            # Wywołujemy funkcję – przekazujemy user_manager
            await selected["func"](user_manager)
        else:
            log_error("Nieprawidłowy wybór.")
            await asyncio.sleep(1)

# Nowa wersja funkcji zarządzania kontami dla danego banku Social Media
async def social_media_account_manager(sm_type, user_manager: UserManager):
    # Pobieramy nazwę i klasę banku – założenie, że SOCIAL_MEDIA_BANK_TYPES jest zdefiniowany
    social_media_name, social_media_class = banks.SOCIAL_MEDIA_BANK_TYPES[sm_type]
    social_media_instance = social_media_class()

    # Tworzymy bazowy ciąg uprawnień uwzględniający bank (np. "admin.social_media.bank.tiktok")
    base_perm = f"admin.social_media.{social_media_name.lower()}"
    base_dev = f"dev.social_media.{social_media_name.lower()}"

    # Definicje funkcji odpowiadających poszczególnym opcjom menu.
    async def copy_task():
        async with ClientSession() as session:
            active_workers = await get_active_workers(session)
        if not active_workers:
            error_animation("Brak aktywnych pracowników.")
            return
        print(Fore.CYAN + "\nDostępne konta pracownicze:")
        for idx, worker in enumerate(active_workers, start=1):
            print(f"{idx}. {worker['sub_id']}")
        print("0. Wszystkie (all)")
        worker_choice = input(Fore.CYAN + "\nWybierz pracownika lub wpisz 'all': " + Style.RESET_ALL).strip()
        if worker_choice.lower() == "all":
            selected_workers = [worker["id"] for worker in active_workers]
        else:
            try:
                selected_index = int(worker_choice) - 1
                selected_workers = [active_workers[selected_index]["id"]]
            except (ValueError, IndexError):
                error_animation("Niepoprawny wybór subid.")
                return
        task_url = input(Fore.CYAN + "Podaj adres URL strony: " + Style.RESET_ALL).strip()
        if not task_url:
            error_animation("Adres URL jest wymagany.")
            return
        execution_time = input(Fore.CYAN + "Podaj czas wykonania zadania (lub naciśnij Enter, aby wykonać teraz): " + Style.RESET_ALL).strip()
        special_attributes = {"url": task_url}
        try:
            async with ClientSession() as session:
                user_manager.user_ip = await user_manager.get_user_ip(session)
                await create_task(
                    session, 
                    TaskType.TT_COPY_ACCOUNT_DATA, 
                    selected_workers, 
                    execution_time, 
                    user_manager.user_id, 
                    user_manager.user_ip, 
                    special_attributes
                )
            log_success("Zadanie zostało zlecone.")
        except Exception as e:
            log_error(f"Błąd podczas zlecania zadania: {str(e)}")
            error_animation("Nie udało się zlecić zadania.")

    async def view_accounts():
        social_media_instance.view_accounts()

    async def export_accounts():
        filename = input(Fore.CYAN + "Nazwa pliku eksportu (domyślnie accounts.txt): " + Style.RESET_ALL) or "accounts.txt"
        social_media_instance.export_to_file(filename)

    async def import_accounts():
        filename = input(Fore.CYAN + "Nazwa pliku importu (domyślnie accounts.txt): " + Style.RESET_ALL) or "accounts.txt"
        social_media_instance.load_from_file(filename)

    async def delete_account():
        account_name = input(Fore.CYAN + "Podaj nazwę użytkownika do usunięcia: " + Style.RESET_ALL)
        social_media_instance.delete_account(account_name)

    # Budujemy menu opcji – każdy wpis ma uprawnienie zbudowane na bazie banku, np.:
    # "admin.social_media.bank.tiktok.copy.task" dla banku TikTok.
    options = [
        {
            "text": "Kopiuj dane kont (zadanie)",
            "permission": f"{base_perm}.copy.task",
            "func": copy_task
        }]
    if user_manager.has_permission(base_dev):
        options.append(
        {
            "text": "Wyświetl zapisane konta",
            "permission": f"{base_dev}.view",
            "func": view_accounts
        },
        {
            "text": "Eksportuj konta do pliku",
            "permission": f"{base_dev}.export",
            "func": export_accounts
        },
        {
            "text": "Importuj konta z pliku",
            "permission": f"{base_dev}.import",
            "func": import_accounts
        },
        {
            "text": "Usuń konto",
            "permission": f"{base_dev}.delete",
            "func": delete_account
        })
    options.append({"text": "Powrót", "permission": None, "func": None})

    while True:
        display_menu(options, social_media_name)
        choice = input(Fore.CYAN + "\nWybierz opcję (1-7): " + Style.RESET_ALL).strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if idx < 0 or idx >= len(options):
                log_error("Nieprawidłowy wybór.")
                continue
            selected = options[idx]
            if selected["text"] == "Powrót":
                break
            perm = selected.get("permission")
            if perm and not user_manager.has_permission(perm):
                log_error("Brak uprawnień do tej opcji.")
                await asyncio.sleep(1)
                continue
            await selected["func"]()
        else:
            log_error("Nieprawidłowy wybór.")
            await asyncio.sleep(1)

# --------------------------------------------------------------------------------
# Menu kont e-mail
# Nowa funkcja wyświetlająca menu wyboru typu konta e-mail (na razie tylko Google)
async def mail_bank_menu(user_manager: UserManager):
    email_banks = [
        {"text": "Google", "permission": "admin.email.google", "bank_type": 0},
        {"text": "Tutanota", "permission": "dev.email.google", "bank_type": 1},
        {"text": "Powrót", "permission": None, "bank_type": None}
    ]
    while True:
        display_menu(email_banks, "Wybierz konto email")
        choice = input(Fore.CYAN + "\nWybierz opcję: " + Style.RESET_ALL).strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if idx < 0 or idx >= len(email_banks):
                log_error("Nieprawidłowy wybór.")
                continue
            selected = email_banks[idx]
            if selected["text"] == "Powrót":
                return
            perm = selected.get("permission")
            if perm and not user_manager.has_permission(perm):
                log_error("Brak uprawnień do tej opcji.")
                await asyncio.sleep(1)
                continue
            bank_type = selected["bank_type"]
            # Wywołanie wewnętrznego menu kont e-mail dla wybranego typu
            await mail_bank_menu_inner(bank_type, user_manager)
            break
        else:
            log_error("Nieprawidłowy wybór.")
            await asyncio.sleep(1)

# Przemianowana funkcja – oryginalne menu kont e-mail
async def mail_bank_menu_inner(bank_type, user_manager: UserManager):
    bank_name, bank_class = banks.MAIL_BANK_TYPES[bank_type]
    bank_instance = bank_class()
    base_perm = f"admin.email.{bank_name.lower()}"
    base_dev = f"dev.email.{bank_name.lower()}"

    async def generate_accounts():
        async with ClientSession() as session:
            active_workers = await get_active_workers(session)
        if not active_workers:
            error_animation("Brak aktywnych pracowników.")
            return
        print(Fore.CYAN + "\nDostępne konta pracownicze:")
        for idx, worker in enumerate(active_workers, start=1):
            print(f"{idx}. {worker['sub_id']}")
        print("0. Wszystkie (all)")
        worker_choice = input(Fore.CYAN + "\nWybierz pracownika lub wpisz 'all': " + Style.RESET_ALL).strip()
        if worker_choice.lower() == "all":
            selected_workers = [worker["id"] for worker in active_workers]
        else:
            try:
                selected_index = int(worker_choice) - 1
                selected_workers = [active_workers[selected_index]["id"]]
            except (ValueError, IndexError):
                error_animation("Niepoprawny wybór subid.")
                return
        execution_time = input(
            Fore.CYAN + "Podaj czas wykonania zadania (lub naciśnij Enter, aby wykonać teraz): " + Style.RESET_ALL
        ).strip()
        try:
            async with ClientSession() as session:
                user_manager.user_ip = await user_manager.get_user_ip(session)
                await create_task(
                    session, 
                    TaskType.G_GENERATE_ACCOUNT, 
                    selected_workers, 
                    execution_time, 
                    user_manager.user_id, 
                    user_manager.user_ip
                )
            log_success("Zadanie zostało zlecone.")
        except Exception as e:
            log_error(f"Błąd podczas zlecania zadania: {str(e)}")
            error_animation("Nie udało się zlecić zadania.")

    async def view_accounts():
        bank_instance.view_accounts()

    async def export_accounts():
        filename = input(
            Fore.CYAN + "Nazwa pliku eksportu (domyślnie accounts.txt): " + Style.RESET_ALL
        ) or "accounts.txt"
        bank_instance.export_to_file(filename)

    async def import_accounts():
        filename = input(
            Fore.CYAN + "Nazwa pliku importu (domyślnie accounts.txt): " + Style.RESET_ALL
        ) or "accounts.txt"
        bank_instance.load_from_file(filename)

    async def delete_account():
        email = input(Fore.CYAN + "Podaj e-mail do usunięcia: " + Style.RESET_ALL)
        bank_instance.delete_account(email)

    options = [
        {
            "text": f"Generuj {bank_name}",
            "permission": f"{base_perm}.generate",
            "func": generate_accounts
        }]
    if user_manager.has_permission(base_dev):
        options.append(
        {
            "text": "Wyświetl zapisane konta",
            "permission": f"{base_dev}.view",
            "func": view_accounts
        },
        {
            "text": "Eksportuj konta do pliku",
            "permission": f"{base_dev}.export",
            "func": export_accounts
        },
        {
            "text": "Importuj konta z pliku",
            "permission": f"{base_dev}.import",
            "func": import_accounts
        },
        {
            "text": "Usuń konto",
            "permission": f"{base_dev}.delete",
            "func": delete_account
        })
    options.append({"text": "Powrót do głównego menu", "permission": None, "func": None})

    while True:
        display_menu(options, f"Bank {bank_name}")
        choice = input(Fore.CYAN + f"\nWybierz opcję (1-{len(options)}): " + Style.RESET_ALL).strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if idx < 0 or idx >= len(options):
                log_error("Nieprawidłowy wybór.")
                continue
            selected = options[idx]
            if selected["text"] == "Powrót do głównego menu":
                break
            perm = selected.get("permission")
            if perm and not user_manager.has_permission(perm):
                log_error("Brak uprawnień do tej opcji.")
                await asyncio.sleep(1)
                continue
            await selected["func"]()
        else:
            log_error("Nieprawidłowy wybór.")
            await asyncio.sleep(1)

# --------------------------------------------------------------------------------
# Menu ustawień
async def settings_menu(user_manager: UserManager):
    if not user_manager.has_permission("admin.settings.modify"):
        log_error("Brak uprawnień do ustawień.")
        await asyncio.sleep(2)
        return
    options = [
        {"text": "Sprawdź aktualizacje dla pracowników", "permission": "admin.settings.update_for_workers", "func": check_updates},
        {"text": "Powrót", "permission": None, "func": None}
    ]
    while True:
        display_menu(options, "Ustawienia (Admin)")
        choice = input(Fore.CYAN + "\nWybierz opcję (1-3): " + Style.RESET_ALL).strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if idx < 0 or idx >= len(options):
                log_error("Nieprawidłowy wybór.")
                continue
            selected = options[idx]
            if selected["text"] == "Powrót":
                break
            perm = selected.get("permission")
            if perm and not user_manager.has_permission(perm):
                log_error("Brak uprawnień do tej opcji.")
                await asyncio.sleep(1)
                continue
            await selected["func"](user_manager)
        else:
            log_error("Nieprawidłowy wybór.")

# --------------------------------------------------------------------------------
# Przykładowe funkcje – implementacje
async def social_media_copy(user_manager: UserManager):
    log_info("Funkcja kopiowania kont Social Media (Admin) wywołana.")
    await asyncio.sleep(1)

async def social_media_view(user_manager: UserManager):
    log_info("Wyświetlanie zapisanych kont Social Media (Admin).")
    await asyncio.sleep(1)

async def social_media_export(user_manager: UserManager):
    log_info("Eksportowanie kont Social Media (Admin).")
    await asyncio.sleep(1)

async def social_media_import(user_manager: UserManager):
    log_info("Importowanie kont Social Media (Admin).")
    await asyncio.sleep(1)

async def social_media_delete(user_manager: UserManager):
    log_info("Usuwanie kont Social Media (Admin).")
    await asyncio.sleep(1)

async def email_generate(user_manager: UserManager):
    log_info("Generowanie kont e-mail (Admin).")
    await asyncio.sleep(1)

async def email_view(user_manager: UserManager):
    log_info("Wyświetlanie kont e-mail (Admin).")
    await asyncio.sleep(1)

async def email_export(user_manager: UserManager):
    log_info("Eksportowanie kont e-mail (Admin).")
    await asyncio.sleep(1)

async def email_import(user_manager: UserManager):
    log_info("Importowanie kont e-mail (Admin).")
    await asyncio.sleep(1)

async def email_delete(user_manager: UserManager):
    log_info("Usuwanie kont e-mail (Admin).")
    await asyncio.sleep(1)

async def check_updates(user_manager: UserManager):
    async with ClientSession() as session:
        await create_task(session, TaskType.CHECK_FOR_UPDATES, ["all"], None, user_manager.user_id, user_manager.user_ip)

async def author_info(user_manager: UserManager):
    clear_console()
    print(Fore.CYAN + "Administrator & Deweloper SocialFlow: D.W." + Style.RESET_ALL)
    input(Fore.CYAN + "\nNaciśnij Enter, aby wrócić...")

async def exit_cleanup(user_manager: UserManager):
    try:
        await cleanup(user_manager.user_id, user_manager.account_type)
        log_info("Cleanup zakończony pomyślnie.")
    except Exception as e:
        log_error(f"Cleanup failed: {e}")
    # Krótkie opóźnienie, aby upewnić się, że logi zostaną zapisane
    await asyncio.sleep(0.1)

# --------------------------------------------------------------------------------
# Główne menu administratora – rozszerzone o nową zakładkę "Bank Social Media"
async def admin_main_menu(user_manager: UserManager):
    options = [
        {"text": "Social Media", "permission": "admin.social_media.bank", "func": social_media_bank_menu},
        {"text": "Konta E-mail", "permission": "admin.email.view", "func": mail_bank_menu},
        {"text": "Ustawienia", "permission": "admin.settings.modify", "func": settings_menu},
        {"text": "Informacje o autorze", "permission": "admin.info.view", "func": author_info},
        {"text": "Wyjście", "permission": None, "func": exit_cleanup}
    ]
    while True:
        display_menu(options, "Menu Admina")
        choice = input(Fore.CYAN + "\nWybierz opcję: " + Style.RESET_ALL).strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if idx < 0 or idx >= len(options):
                log_error("Nieprawidłowy wybór.")
                continue
            selected = options[idx]
            if selected["text"] == "Wyjście":
                log_info("Zamykanie panelu administratora.")
                await selected["func"](user_manager)
                return
            perm = selected.get("permission")
            if perm and not user_manager.has_permission(perm):
                log_error("Brak uprawnień do tej opcji.")
                await asyncio.sleep(1)
                continue
            await selected["func"](user_manager)
        else:
            log_error("Nieprawidłowy wybór.")

async def main_menu(user_manager: UserManager):
    await admin_main_menu(user_manager)