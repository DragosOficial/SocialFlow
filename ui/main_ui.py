import os
import time
from colorama import Fore, Style, init
from utils.utils import clear_console, log_info, log_error, log_success
from automation import email_account, social_media
from network.firebase_client import set_account_state, create_task, TaskType, get_active_workers
from core.user_manager import UserManager
from utils.banks import MAIL_BANK_TYPES, SOCIAL_MEDIA_BANK_TYPES
from aiohttp import ClientSession 
import asyncio

# Inicjalizacja kolorów terminala
init(autoreset=True)

# ASCII logo
SOCIALFLOW_ASCII = """
 ██████╗ █████╗  █████╗ ██╗ █████╗ ██╗        ███████╗██╗      █████╗  ██╗       ██╗
██╔════╝██╔══██╗██╔══██╗██║██╔══██╗██║        ██╔════╝██║     ██╔══██╗ ██║  ██╗  ██║
╚█████╗ ██║  ██║██║  ╚═╝██║███████║██║        █████╗  ██║     ██║  ██║ ╚██╗████╗██╔╝
 ╚═══██╗██║  ██║██║  ██╗██║██╔══██║██║        ██╔══╝  ██║     ██║  ██║  ████╔═████║ 
██████╔╝╚█████╔╝╚█████╔╝██║██║  ██║███████╗   ██║     ███████╗╚█████╔╝  ╚██╔╝ ╚██╔╝ 
╚═════╝  ╚════╝  ╚════╝ ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝     ╚══════╝ ╚════╝    ╚═╝   ╚═╝  
"""

# Animacje
def error_animation(message):
    for _ in range(3):
        print(Fore.RED + message + Style.RESET_ALL, end="\r")
        time.sleep(0.3)
        print(" " * len(message), end="\r")
        time.sleep(0.3)
    print(Fore.RED + message + Style.RESET_ALL)

def loading_animation(message):
    for _ in range(3):
        for dots in range(4):
            print(Fore.YELLOW + message + "." * dots + " " * (3 - dots), end="\r")
            time.sleep(0.4)
    print(Fore.LIGHTGREEN_EX + message + Style.RESET_ALL)

async def closing_animation():
    print(Fore.RED + "\nZamykanie programu... Dziękuję za skorzystanie z SocialFlow!" + Style.RESET_ALL)
    user_manager = UserManager()
    await set_account_state(user_manager.user_id, user_manager.account_type, False)
    clear_console()

# Menu główne
def display_menu(options, title):
    clear_console()
    print(Fore.LIGHTMAGENTA_EX + SOCIALFLOW_ASCII + Style.RESET_ALL)
    print(Fore.LIGHTBLUE_EX + f"\n============ {title.upper()} ============" + Style.RESET_ALL)
    for num, desc in options:
        print(f" {num}. {Fore.LIGHTGREEN_EX}{desc}" + Style.RESET_ALL)
    print(Fore.LIGHTBLUE_EX + "=" * 34 + Style.RESET_ALL)

async def main_menu():
    options = [
        (Fore.YELLOW + "1", "Social Media"),
        (Fore.YELLOW + "2", "Adresy E-mail"),
        (Fore.YELLOW + "3", "Autor"),
        (Fore.YELLOW + "4", "Ustawienia"),
        (Fore.RED + "5", "Wyjście" + Style.RESET_ALL)
    ]
    while True:
        display_menu(options, "Menu")
        choice = input(Fore.CYAN + "\nWybierz opcję (1-5): " + Style.RESET_ALL).strip()
        if choice == "1":
            await sm_menu()
        elif choice == "2":
            await bank_kont()
        elif choice == "3":
            author_info()
        elif choice == "4":
            await settings_menu()
        elif choice == "5":
            await closing_animation()
            os._exit(0)
        else:
            error_animation("Nieprawidłowy wybór.")

async def sm_menu():
    options = [
        (Fore.YELLOW + "1", "TikTok"),
        (Fore.YELLOW + "2", "Instagram"),
        (Fore.YELLOW + "3", "X (dawniej Twitter)"),
        (Fore.YELLOW + "4", "YouTube"),
        (Fore.RED + "5", "Powrót do głównego menu")
    ]
    while True:
        display_menu(options, "Social Media")
        choice = input(Fore.CYAN + "\nWybierz opcję (1-5): " + Style.RESET_ALL).strip()
        if choice in ["1", "2", "3", "4"]:
            await social_media_account_manager(int(choice) - 1)
        elif choice == "5":
            return
        else:
            error_animation("Nieprawidłowy wybór.")

async def social_media_account_manager(sm_type):
    social_media_name, social_media_class = SOCIAL_MEDIA_BANK_TYPES[sm_type]
    social_media_instance = social_media_class()
    options = [
        (Fore.YELLOW + "1", "Kopiuj dane kont"),
        (Fore.YELLOW + "3", "Wyświetl zapisane konta"),
        (Fore.YELLOW + "4", "Eksportuj konta do pliku"),
        (Fore.YELLOW + "5", "Importuj konta z pliku"),
        (Fore.YELLOW + "6", "Usuń konto"),
        (Fore.RED + "7", "Powrót do głównego menu")
    ]
    while True:
        display_menu(options, f"{social_media_name}")
        choice = input(Fore.CYAN + "\nWybierz opcję (1-7): " + Style.RESET_ALL).strip()
        try:
            if choice == "1":
                # Pobieranie aktywnych pracowników
                async with ClientSession() as session:
                    active_workers = await get_active_workers(session)

                if not active_workers:
                    error_animation("Brak aktywnych pracowników.")
                    continue

                print(Fore.CYAN + "\nDostępne konta pracownicze:")
                for idx, worker in enumerate(active_workers, start=1):
                    print(f"{idx}. {worker['sub_id']}")
                print("0. Wszystkie (all)")

                worker_choice = input(Fore.CYAN + "\nWybierz pracownika lub wpisz 'all': " + Style.RESET_ALL).strip()
                if worker_choice.lower() == "all":
                    selected_workers = [worker["id"] for worker in active_workers]  # Lista wszystkich pracowników
                else:
                    try:
                        selected_index = int(worker_choice) - 1
                        selected_workers = [active_workers[selected_index]["id"]]  # Lista z jednym wybranym pracownikiem
                    except (ValueError, IndexError):
                        error_animation("Niepoprawny wybór subid.")
                        continue

                # Prośba o podanie URL
                task_url = input(Fore.CYAN + "Podaj adres URL strony: " + Style.RESET_ALL).strip()
                if not task_url:
                    error_animation("Adres URL jest wymagany.")
                    continue

                # Prośba o czas wykonania zadania
                execution_time = input(Fore.CYAN + "Podaj czas wykonania zadania (lub naciśnij Enter, aby wykonać teraz): " + Style.RESET_ALL).strip()
                
                special_attributes = {
                    "url": task_url
                }

                try:
                    async with ClientSession() as session:
                        user_manager = UserManager()
                        user_manager.user_ip = await user_manager.get_user_ip(session)
                        await create_task(session, TaskType.T_COPY_ACCOUNT_DATA, selected_workers, execution_time, user_manager.user_id, user_manager.user_ip, special_attributes)
                    log_success("Zadanie zostało zlecone.")
                except Exception as e:
                    log_error(f"Błąd podczas zlecania zadania: {str(e)}")
                    error_animation("Nie udało się zlecić zadania.")
            if choice == "2":
                # Prośba o link po wybraniu opcji 1
                video_link = input(Fore.CYAN + f"Podaj link do filmu: " + Style.RESET_ALL).strip()
                if video_link:
                    social_media_instance.copy_accounts(video_link)
                else:
                    error_animation("Nie podano linku.")
            elif choice == "3":
                social_media_instance.view_accounts()
            elif choice == "4":
                filename = input(Fore.CYAN + "Nazwa pliku eksportu (domyślnie accounts.txt): " + Style.RESET_ALL) or "accounts.txt"
                social_media_instance.export_to_file(filename)
            elif choice == "5":
                filename = input(Fore.CYAN + "Nazwa pliku importu (domyślnie accounts.txt): " + Style.RESET_ALL) or "accounts.txt"
                social_media_instance.load_from_file(filename)
            elif choice == "6":
                account_name = input(Fore.CYAN + "Podaj nazwę użytkownika do usunięcia: " + Style.RESET_ALL)
                social_media_instance.delete_account(account_name)
            elif choice == "7":
                return
            else:
                error_animation("Nieprawidłowy wybór.")
        except Exception as e:
            error_animation(f"Błąd: {str(e)}")

async def bank_kont():
    options = [
        (Fore.YELLOW + "1", "Bank Gmaili"),
        (Fore.YELLOW + "2", "Bank Onet"),
        (Fore.YELLOW + "3", "Bank Proton"),
        (Fore.YELLOW + "4", "Bank Tutanota"),
        (Fore.RED + "5", "Powrót do menu głównego")
    ]
    while True:
        display_menu(options, "Bank Kont")
        choice = input(Fore.CYAN + "\nWybierz opcję (1-5): " + Style.RESET_ALL).strip()
        if choice in ["1", "2", "3", "4"]:
            await bank_menu(int(choice) - 1)
        elif choice == "5":
            return
        else:
            error_animation("Nieprawidłowy wybór.")

# Menu konkretnego banku
async def bank_menu(bank_type):
    bank_name, bank_class = MAIL_BANK_TYPES[bank_type]
    bank_instance = bank_class()
    options = [
        (Fore.YELLOW + "1", f"Generuj {bank_name}"),
        (Fore.YELLOW + "2", "Wyświetl zapisane konta"),
        (Fore.YELLOW + "3", "Eksportuj konta do pliku"),
        (Fore.YELLOW + "4", "Importuj konta z pliku"),
        (Fore.YELLOW + "5", "Usuń konto"),
        (Fore.RED + "6", "Powrót do głównego menu")
    ]
    while True:
        display_menu(options, f"Bank {bank_name}")
        choice = input(Fore.CYAN + "\nWybierz opcję (1-6): " + Style.RESET_ALL).strip()
        try:
            if choice == "1":
                # Pobieranie aktywnych pracowników
                async with ClientSession() as session:
                    active_workers = await get_active_workers(session)

                if not active_workers:
                    error_animation("Brak aktywnych pracowników.")
                    continue

                print(Fore.CYAN + "\nDostępne konta pracownicze:")
                for idx, worker in enumerate(active_workers, start=1):
                    print(f"{idx}. {worker['sub_id']}")
                print("0. Wszystkie (all)")

                worker_choice = input(Fore.CYAN + "\nWybierz pracownika lub wpisz 'all': " + Style.RESET_ALL).strip()
                if worker_choice.lower() == "all":
                    selected_workers = [worker["id"] for worker in active_workers]  # Lista wszystkich pracowników
                else:
                    try:
                        selected_index = int(worker_choice) - 1
                        selected_workers = [active_workers[selected_index]["id"]]  # Lista z jednym wybranym pracownikiem
                    except (ValueError, IndexError):
                        error_animation("Niepoprawny wybór subid.")
                        continue

                # Prośba o czas wykonania zadania
                execution_time = input(Fore.CYAN + "Podaj czas wykonania zadania (lub naciśnij Enter, aby wykonać teraz): " + Style.RESET_ALL).strip()

                try:
                    async with ClientSession() as session:
                        user_manager = UserManager()
                        user_manager.user_ip = await user_manager.get_user_ip(session)
                        await create_task(session, TaskType.G_GENERATE_ACCOUNT, selected_workers, execution_time, user_manager.user_id, user_manager.user_ip)
                    log_success("Zadanie zostało zlecone.")
                except Exception as e:
                    log_error(f"Błąd podczas zlecania zadania: {str(e)}")
                    error_animation("Nie udało się zlecić zadania.")
            elif choice == "2":
                bank_instance.view_accounts()
            elif choice == "3":
                filename = input(Fore.CYAN + "Nazwa pliku eksportu (domyślnie accounts.txt): " + Style.RESET_ALL) or "accounts.txt"
                bank_instance.export_to_file(filename)
            elif choice == "4":
                filename = input(Fore.CYAN + "Nazwa pliku importu (domyślnie accounts.txt): " + Style.RESET_ALL) or "accounts.txt"
                bank_instance.load_from_file(filename)
            elif choice == "5":
                email = input(Fore.CYAN + "Podaj e-mail do usunięcia: " + Style.RESET_ALL)
                bank_instance.delete_account(email)
            elif choice == "6":
                return
            else:
                error_animation("Nieprawidłowy wybór.")
        except Exception as e:
            error_animation(f"Błąd: {str(e)}")

# Informacje o autorze
def author_info():
    clear_console()
    print(Fore.LIGHTMAGENTA_EX + SOCIALFLOW_ASCII + Style.RESET_ALL)
    print(Fore.CYAN + "Autor programu: Dawid Wielechowski\n" + Style.RESET_ALL)
    print(Fore.LIGHTGREEN_EX +
          "Krótki opis: Twórca rozwiązań informatycznych oraz entuzjasta alkoholu.\n" + Style.RESET_ALL)
    print(Fore.YELLOW + "Kontakt: dawid.wielechowski@example.com" + Style.RESET_ALL)
    print(Fore.YELLOW + "Profil LinkedIn: https://linkedin.com/in/dawidwielechowski" + Style.RESET_ALL)
    print(Fore.YELLOW + "GitHub: https://github.com/dawidwielechowski" + Style.RESET_ALL)
    print(Fore.LIGHTBLUE_EX + "\n" + "="*40 + "\n" + Style.RESET_ALL)

    input(Fore.CYAN + "\nNaciśnij Enter, aby wrócić do menu głównego..." + Style.RESET_ALL)
    main_menu()

async def settings_menu():
    options = [
        (Fore.YELLOW + "1", "Zarządaj sprawdzenia aktualizacji dla wszystkich kont pracowniczych"),
        (Fore.RED + "2", "Powrót" + Style.RESET_ALL)
    ]
    while True:
        display_menu(options, "ustawienia")
        choice = input(Fore.CYAN + "\nWybierz opcję (1-2): " + Style.RESET_ALL).strip()
        try:
            if choice == "1":
                async with ClientSession() as session:
                    user_manager = UserManager()
                    await create_task(session, TaskType.CHECK_FOR_UPDATES, ["all"], assigned_by_id = user_manager.user_id, assigned_by_ip = user_manager.user_ip)
                    await asyncio.sleep(2)
            elif choice == "2":
                return
            else:
                error_animation("Nieprawidłowy wybór.")
        except Exception as e:
            error_animation(f"Błąd: {str(e)}")