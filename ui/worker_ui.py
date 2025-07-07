import os
import asyncio
import time
from colorama import Fore, Style, init
from utils.utils import clear_console, log_info, log_error, log_success
from utils import banks
from aiohttp import ClientSession
from network.firebase_client import create_task, TaskType, TaskMonitor, cleanup, FirestoreClient
from core.user_manager import UserManager
from utils.tasks import ReportTypeMain, ReportTypeSubPrzemoc, ReportTypeSubNagosc, ReportTypeSubNienawisc

init(autoreset=True)

# Przykładowe logo panelu pracownika
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

def display_menu(options, title):
    clear_console()
    print(Fore.LIGHTMAGENTA_EX + SOCIALFLOW_ASCII + Style.RESET_ALL)
    print(Fore.LIGHTBLUE_EX + f"\n============ {title.upper()} ============" + Style.RESET_ALL)
    for index, option in enumerate(options, start=1):
        num_color = Fore.RED if index == len(options) else Fore.YELLOW
        print(f" {num_color}{index}.{Style.RESET_ALL} {Fore.LIGHTGREEN_EX}{option['text']}")
    print(Fore.LIGHTBLUE_EX + "=" * (len(title) + 22) + Style.RESET_ALL)

async def wait_for_enter(prompt: str, monitor: TaskMonitor):
    while monitor.is_task_running:
        await asyncio.sleep(0.5)
    # Gdy żadne zadanie nie działa, czekamy na Enter
    await asyncio.to_thread(input, prompt)
    # Krótkie opóźnienie, aby "wypłukać" ewentualne dodatkowe naciśnięcia
    await asyncio.sleep(0.2)


async def tt_copy_direct(user_manager: UserManager):
    if not user_manager.has_permission("worker.social_media.tiktok.copy.direct"):
        log_error("Brak uprawnień do zadań.")
        await asyncio.sleep(2)
        return
    async with ClientSession() as session:
        url = (await asyncio.to_thread(input, Fore.CYAN + "Podaj link do filmu: " + Style.RESET_ALL)).strip()
        if url:
            special_attributes = {"url": url}
            await create_task(session, TaskType.TT_COPY_ACCOUNT_DATA, [user_manager.user_id],
                              None, user_manager.user_id, user_manager.user_ip, special_attributes)
        else:
            error_animation("Nie podano linku.")

async def tt_mass_report_direct(user_manager: UserManager):
    if not user_manager.has_permission("worker.social_media.tiktok.copy.direct"):
        log_error("Brak uprawnień do zadań.")
        await asyncio.sleep(2)
        return
    async with ClientSession() as session:
        url = (await asyncio.to_thread(input, Fore.CYAN + "Podaj link do filmu: " + Style.RESET_ALL)).strip()
        if not url:
            error_animation("Nie podano linku.")
            return

        report_count = (await asyncio.to_thread(input, Fore.CYAN + "Ile razy ma zreportować film: " + Style.RESET_ALL)).strip()
        
        # Wyświetlenie opcji wyboru dla głównego typu zgłoszenia (ReportTypeMain)
        print(Fore.YELLOW + "Wybierz typ zgłoszenia:" + Style.RESET_ALL)
        main_enum_list = list(ReportTypeMain)
        for i, report_type in enumerate(main_enum_list, start=1):
            print(f"{i}. {report_type.value}")
        
        main_choice_str = (await asyncio.to_thread(input, Fore.CYAN + "Wprowadź numer wyboru: " + Style.RESET_ALL)).strip()
        try:
            main_choice_index = int(main_choice_str)
            if not (1 <= main_choice_index <= len(main_enum_list)):
                log_error("Niepoprawny numer wyboru głównego typu zgłoszenia.")
                return
            main_report_choice = main_enum_list[main_choice_index - 1]
        except Exception as e:
            log_error("Błąd podczas wybierania głównego typu zgłoszenia.")
            return
        
        sub_report_choice = None
        # Jeśli wybrano typ, dla którego dostępny jest podenum, zapytaj o wybór podtypu
        if main_report_choice in (ReportTypeMain.PRZEMOC, ReportTypeMain.NIENAWISC, ReportTypeMain.NAGOSC):
            if main_report_choice == ReportTypeMain.PRZEMOC:
                sub_enum_list = list(ReportTypeSubPrzemoc)
            elif main_report_choice == ReportTypeMain.NIENAWISC:
                sub_enum_list = list(ReportTypeSubNienawisc)
            elif main_report_choice == ReportTypeMain.NAGOSC:
                sub_enum_list = list(ReportTypeSubNagosc)
            else:
                sub_enum_list = []
            
            if sub_enum_list:
                print(Fore.YELLOW + "Wybierz podtyp zgłoszenia:" + Style.RESET_ALL)
                for i, sub_report in enumerate(sub_enum_list, start=1):
                    print(f"{i}. {sub_report.value}")
                sub_choice_str = (await asyncio.to_thread(input, Fore.CYAN + "Wprowadź numer wyboru: " + Style.RESET_ALL)).strip()
                try:
                    sub_choice_index = int(sub_choice_str)
                    if not (1 <= sub_choice_index <= len(sub_enum_list)):
                        log_error("Niepoprawny numer wyboru podtypu zgłoszenia.")
                        return
                    sub_report_choice = sub_enum_list[sub_choice_index - 1]
                except Exception as e:
                    log_error("Błąd podczas wybierania podtypu zgłoszenia.")
                    return
        
        special_attributes = {
            "url": url,
            "report_count": report_count,
            "main_report_choice": main_report_choice.value
        }
        if sub_report_choice:
            special_attributes["sub_report_choice"] = sub_report_choice.value
        
        await create_task(session, TaskType.TT_MASS_REPORT, [user_manager.user_id],
                          None, user_manager.user_id, user_manager.user_ip, special_attributes)

async def g_generate_direct(user_manager: UserManager):
    if not user_manager.has_permission("worker.email.google.generate"):
        log_error("Brak uprawnień do zadań.")
        await asyncio.sleep(2)
        return
    async with ClientSession() as session:
        await create_task(session, TaskType.G_GENERATE_ACCOUNT, [user_manager.user_id],
                           None, user_manager.user_id, user_manager.user_ip)

async def account_info(user_manager: UserManager):
    clear_console()
    print(Fore.CYAN + "Informacje o koncie (Worker):" + Style.RESET_ALL)
    print(f"ID: {user_manager.user_id}")
    print(f"IP: {user_manager.user_ip}")
    print(f"Uprawnienia: {user_manager.permissions}")
    await asyncio.to_thread(input, Fore.CYAN + "\nNaciśnij Enter, aby powrócić..." + Style.RESET_ALL)

async def exit_cleanup(user_manager: UserManager):
    try:
        await cleanup(user_manager.user_id, user_manager.account_type)
        log_info("Cleanup zakończony pomyślnie.")
    except Exception as e:
        log_error(f"Cleanup failed: {e}")
    # Krótkie opóźnienie, aby upewnić się, że logi zostaną zapisane
    await asyncio.sleep(0.1)

# Główne menu panelu pracownika – "wyłącza" UI przed wykonaniem zadania, a po jego zakończeniu wznawia UI
async def worker_main_menu(user_manager: UserManager):
    client = FirestoreClient()
    monitor = TaskMonitor(client, user_manager.user_id)
    # Uruchamiamy monitor zadań jako zadanie w tle
    asyncio.create_task(monitor.start())
    
    options = [
        {"text": "Informacje o koncie", "permission": "worker.info.view", "func": account_info},
    ]
    if user_manager.has_permission("worker.social_media.tiktok.copy.direct"):
        options.append({
            "text": "Kopiuj dane kont z TikToka (zadanie lokalne)",
            "permission": "worker.social_media.tiktok.copy.direct",
            "func": tt_copy_direct
        })
    if user_manager.has_permission("worker.social_media.tiktok.mass_report.direct"):
        options.append({
            "text": "Mass report z losowo wybranych kont TikTok (zadanie lokalne)",
            "permission": "worker.social_media.tiktok.mass_report.direct",
            "func": tt_mass_report_direct
        })
    if user_manager.has_permission("worker.email.google.generate"):
        options.append({
            "text": "Generuj konto Google (zadanie lokalne)",
            "permission": "worker.email.google.generate",
            "func": g_generate_direct
        })
    options.append({"text": "Wyjście", "permission": None, "func": exit_cleanup})

    while True:
        # Jeśli zadanie jest w trakcie wykonywania, blokujemy wejście do menu.
        if monitor.is_task_running:
            await asyncio.sleep(1)
            continue

        display_menu(options, "Menu Pracownika")
        choice = (await asyncio.to_thread(input, Fore.CYAN + "\nWybierz opcję: " + Style.RESET_ALL)).strip()
        if not choice:
            await asyncio.sleep(0.5)
            continue
        if choice.isdigit():
            idx = int(choice) - 1
            if idx < 0 or idx >= len(options):
                log_error("Nieprawidłowy wybór.")
                continue
            selected = options[idx]
            if selected["text"] == "Wyjście":
                await selected["func"](user_manager)
                return
            if selected.get("permission") and not user_manager.has_permission(selected["permission"]):
                log_error("Brak uprawnień do tej opcji.")
                await asyncio.sleep(1)
                continue
            # Przed wykonaniem zadania "blokujemy" interfejs – flaga zostanie ustawiona przez TaskMonitor
            break
        else:
            log_error("Nieprawidłowy wybór.")

    clear_console()
    await selected["func"](user_manager)
    while monitor.is_task_running:
        await asyncio.sleep(1)
    clear_console()
    await worker_main_menu(user_manager)

async def main_menu(user_manager: UserManager):
    await worker_main_menu(user_manager)