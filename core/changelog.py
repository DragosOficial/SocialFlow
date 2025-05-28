import requests
import os
from utils.utils import log_info, log_error
from core.config_manager import ConfigManager
from colorama import Fore, Style

# URL do pobierania changelogu
CHANGELOG_URL = "https://drive.google.com/uc?export=download&id=1WpOKUnDOJiFYOuXXqTGvbaIghLqRwfji"


def get_changelog():
    """Pobiera changelog z Google Drive."""
    try:
        response = requests.get(CHANGELOG_URL, timeout=10)
        response.raise_for_status()
        log_info("Changelog został pobrany pomyślnie.")

        # Odczytaj tekst z odpowiednim kodowaniem
        # Użyj decode zamiast text
        return response.content.decode('utf-8').strip()
    except requests.RequestException as e:
        log_error(f"Błąd podczas pobierania changelogu: {e}")
        return None

# Funkcja inicjalizująca pobieranie changelogu


def initialize_changelog():
    """Inicjalizuje proces pobierania changelogu."""
    config = config_manager.config
    changelog = get_changelog()

    if changelog:
        # Jeśli changelog został pobrany, a użytkownik jeszcze go nie widział
        if not config.get("changelog_viewed"):
            os.system("cls" if os.name == "nt" else "clear")
            print(f"{Fore.CYAN}============================")
            print(f"{Fore.CYAN}        CHANGELOG")
            print(f"{Fore.CYAN}       SocialFlow ")
            print(f"{Fore.CYAN}============================\n")

            # Wyświetlenie changelogu z kolorami
            changelog_lines = changelog.splitlines()
            for line in changelog_lines:
                if line.startswith("Wersja"):
                    print(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
                elif line.startswith("[Nowości]:") or line.startswith("[Poprawki i ulepszenia]:") or line.startswith("[Naprawione błędy]:"):
                    print(f"{Fore.YELLOW}{line}{Style.RESET_ALL}")
                else:
                    print(line)

            print(f"\nDziękuję za korzystanie z SocialFlow!")
            print(f"Dawid Wielechowski")
            print(f"{Fore.CYAN}============================")

            # Oczekiwanie na naciśnięcie Enter przez użytkownika
            input("\nNaciśnij Enter, aby zamknąć changelog...")

            # Aktualizacja informacji o wyświetleniu changelogu
            config["changelog_viewed"] = True
            # Zapisz zmodyfikowaną konfigurację
            config_manager = ConfigManager()
            config_manager.save_config(config)
            log_info("Status wyświetlenia changelogu zaktualizowany.")
    else:
        log_info("Brak changelogu do wyświetlenia.")

# Ustawianie statusu wyświetlenia changelogu jako 'nie wyświetlony' po aktualizacji


def reset_changelog_viewed():
    """Resetuje status changelogu, aby wyświetlić go po następnej aktualizacji."""
    config_manager = ConfigManager()
    config = config_manager.config  # Użycie config_manager
    config["changelog_viewed"] = False
    config_manager.save_config(config)  # Zapisz zmodyfikowaną konfigurację
    log_info("Zresetowano status wyświetlenia changelogu.")
