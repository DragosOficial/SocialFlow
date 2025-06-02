import asyncio
import ctypes
import os
import sys
import traceback
import win32api

from utils.file_renamer import ensure_correct_filename
import network.updater as updater
from core.user_manager import UserManager
from network.firebase_client import FirestoreClient, FIRESTORE_BASE_URL, API_KEY
from utils.utils import (
    log_error, log_info, start_new_session, clear_console
)
from network.firebase_client import (
    check_connection, AccountType, set_account_state, cleanup_loop
)
from ui import admin_ui, worker_ui
from core.config_manager import ConfigManager, LOCAL_VERSION

class AppRunner:
    def __init__(self):
        self.user_id = None
        self.account_type = None

    def on_console_close(self, event):
        if event == 2:  # CTRL_CLOSE_EVENT
            log_info(f"\nProgram jest zamykany... {self.user_id}")
            try:
                cleanup_loop(self.user_id, self.account_type)
            except Exception as e:
                log_error(f"Cleanup failed: {e}\n{traceback.format_exc()}")
            return True
        return False

    async def set_window_title(self):
        version = LOCAL_VERSION
        static_title = f"Social Flow | {version}"

        if sys.platform == "win32":
            ctypes.windll.kernel32.SetConsoleTitleW(static_title)
        else:
            term = os.environ.get("TERM", "dumb").lower()
            if sys.stdout.isatty() and term != "dumb":
                sys.stdout.write(f"\x1b]2;{static_title}\x07")
                sys.stdout.flush()

    async def initialize_app(self):
        start_new_session(LOCAL_VERSION)
        ConfigManager().config
        await ensure_correct_filename(LOCAL_VERSION)

        async with FirestoreClient(api_key=API_KEY, base_url=FIRESTORE_BASE_URL) as client:
            try:
                await asyncio.gather(
                    updater.check_for_updates(LOCAL_VERSION),
                    check_connection(client)
                )
            except Exception as e:
                log_error(f"Błąd podczas inicjalizacji: {e}\n{traceback.format_exc()}")
                raise


    async def run(self):
        await self.set_window_title()
        await self.initialize_app()

        user_manager = UserManager()
        try:
            self.account_type, self.user_id = await user_manager.run()
        except Exception as e:
            log_error(f"Błąd logowania: {e}\n{traceback.format_exc()}")
            return

        if not self.account_type or not self.user_id:
            log_error("Brak prawidłowego typu konta lub ID użytkownika.")
            return

        clear_console()
        log_info(f"Typ konta: {self.account_type}, ID użytkownika: {self.user_id}")

        try:
            await set_account_state(self.user_id, self.account_type, True)
        except Exception as e:
            log_error(f"Błąd przy ustawianiu stanu konta: {e}\n{traceback.format_exc()}")
            return

        if self.account_type == AccountType.ADMIN:
            await admin_ui.main_menu(user_manager)
        elif self.account_type == AccountType.WORKER:
            await worker_ui.main_menu(user_manager)
        else:
            log_error("Nieautoryzowany dostęp. Zamykanie aplikacji.")


if __name__ == "__main__":
    runner = AppRunner()
    win32api.SetConsoleCtrlHandler(runner.on_console_close, True)

    try:
        asyncio.run(runner.run())
    except Exception as e:
        log_error(f"Nieoczekiwany błąd: {e}\n{traceback.format_exc()}")
        runner.on_console_close(2)
