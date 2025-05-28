import ctypes
import asyncio
import sys
import os
import win32api
import signal
from aiohttp import ClientSession

from utils.file_renamer import ensure_correct_filename
import network.updater as updater
from core.user_manager import UserManager
from utils.utils import log_error, log_info, start_new_session, clear_console
from network.firebase_client import check_connection, AccountType, set_account_state, cleanup_loop
from ui import admin_ui, worker_ui
from core.config_manager import ConfigManager, LOCAL_VERSION
from core.changelog import initialize_changelog

USER_ID = None
ACCOUNT_TYPE = None


def on_console_close(event):
    if event == 2:  # CTRL_CLOSE_EVENT
        log_info(f"\nProgram jest zamykany... {USER_ID}")
        try:
            cleanup_loop(USER_ID, ACCOUNT_TYPE)
        except Exception as e:
            log_error(f"Cleanup failed: {e}")
        # Zwrócenie True informuje system, że zdarzenie zostało obsłużone
        return True
    return False
    

async def set_window_title() -> None:
    """Ustawia statyczny tytuł okna konsoli, jeśli terminal obsługuje sekwencje ANSI."""
    version = LOCAL_VERSION
    static_title = f"Social Flow | {version}"

    if sys.platform == "win32":
        ctypes.windll.kernel32.SetConsoleTitleW(static_title)
    else:
        # Sprawdzamy, czy stdout jest terminalem i czy zmienna TERM wskazuje na terminal obsługujący ANSI
        term = os.environ.get("TERM", "dumb").lower()
        if sys.stdout.isatty() and term != "dumb":
            sys.stdout.write(f"\x1b]2;{static_title}\x07")
            sys.stdout.flush()
        else:
            # Terminal nie wspiera sekwencji ANSI – można opcjonalnie zalogować ten fakt lub po prostu pominąć zmianę tytułu.
            pass


async def initialize_app() -> None:
    """Inicjalizuje aplikację, sprawdzając wymagania wstępne."""
    start_new_session(LOCAL_VERSION)

    config_manager = ConfigManager()
    config_manager.config
    await ensure_correct_filename(LOCAL_VERSION)

    # Uruchomienie dwóch niezależnych zadań równocześnie
    async with ClientSession() as session:
        try:
            await asyncio.gather(
                updater.check_for_updates(LOCAL_VERSION),
                check_connection(session)
            )
        except Exception as e:
            log_error(f"Błąd podczas inicjalizacji: {e}")
            raise


async def main() -> None:
    global USER_ID, ACCOUNT_TYPE
    await set_window_title()
    await initialize_app()

    user_manager = UserManager()
    ACCOUNT_TYPE, USER_ID = await user_manager.run()

    clear_console()
    log_info(f"Typ konta: {ACCOUNT_TYPE}, ID użytkownika: {USER_ID}")

    await set_account_state(USER_ID, ACCOUNT_TYPE, True)

    # Na podstawie typu konta wywołujemy interfejs
    if ACCOUNT_TYPE == AccountType.ADMIN:
        await admin_ui.main_menu(user_manager)
    elif ACCOUNT_TYPE == AccountType.WORKER:
        await worker_ui.main_menu(user_manager)
    else:
        log_info("Nieautoryzowany dostęp. Zamykanie aplikacji.")
        return


if __name__ == "__main__":
    win32api.SetConsoleCtrlHandler(on_console_close, True)

    try:
        asyncio.run(main())
    except Exception as e:
        log_error(f"Nieoczekiwany błąd: {e}")
        on_console_close(2)