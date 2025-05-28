import os
import requests
import time
import subprocess
import zipfile
from utils.utils import log_info, log_success, log_error
from core.config_manager import ConfigManager
from colorama import Fore, Style
from core.changelog import reset_changelog_viewed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

VERSION_URL = "https://drive.google.com/uc?export=download&id=1AB7BQDmwPZ72DHGBzbIFLudj6HF2ojwz"
DOWNLOAD_URL_TEMPLATE = "https://drive.google.com/uc?export=download&id=12XPeX8sVz_eW6QGvjakydPUn_UIOGovS"


def get_latest_version():
    """Pobiera najnowszą wersję z pliku na Google Drive."""
    try:
        response = requests.get(VERSION_URL, timeout=10)
        response.raise_for_status()
        return response.text.strip()  # Zakładamy, że tekst zawiera wersję w formacie "1.0.0b"
    except requests.RequestException as e:
        log_error(f"Błąd podczas pobierania najnowszej wersji: {e}")
        return None


def get_download_link_with_chromedriver():
    """Używa Chromedrivera do kliknięcia przycisku i pobrania linku do pliku."""

    options = Options()
    options.add_argument("--headless=new")

    # Uruchomienie webdrivera
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        # Wejdź na stronę z przyciskiem pobierania
        driver.get(DOWNLOAD_URL_TEMPLATE)

        # Czekaj, aż przycisk będzie widoczny (możesz dostosować czas oczekiwania)
        time.sleep(3)

        # Znajdź przycisk pobierania i kliknij go
        download_button = driver.find_element(By.ID, 'uc-download-link')
        download_button.click()

        # Poczekaj chwilę, aby link do pobierania został wygenerowany
        time.sleep(3)

        # Znajdź pełny link z parametrami potwierdzenia
        download_link = driver.current_url

        # Upewnij się, że link zawiera dodatkowy parametr confirm=t
        if "confirm=t" not in download_link:
            download_link += "&confirm=t"

        return download_link
    except Exception as e:
        print(f"Nie udało się uzyskać linku: {e}")
        return None
    finally:
        driver.quit()

def download_new_version(download_link):
    """Pobiera i zapisuje nową wersję programu w formie ZIP."""
    zip_filename = "SocialFlow.zip"

    try:
        # Pobierz plik z wygenerowanego linku
        response = requests.get(download_link, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        total_size_mb = total_size / (1024 * 1024)  # Konwersja do MB
        downloaded_size = 0

        with open(zip_filename, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # Filtruj puste bloki
                    file.write(chunk)
                    downloaded_size += len(chunk)
                    # Aktualizacja postępu
                    downloaded_size_mb = downloaded_size / \
                        (1024 * 1024)  # Konwersja do MB
                    print(
                        f"\r{Fore.BLUE}[!]{Style.RESET_ALL} Pobieranie aktualizacji: {downloaded_size_mb:.2f} MB/{total_size_mb:.2f} MB", end='')

        print()  # Przełamanie linii po zakończeniu pobierania
        log_success(f"Pobrano nową wersję: {zip_filename}")
        return zip_filename
    except requests.RequestException as e:
        log_error(f"Błąd podczas pobierania nowej wersji: {e}")
        return None

def unzip_file(zip_filename):
    """Rozpakowuje plik ZIP."""
    try:
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall()  # Rozpakowuje do bieżącego katalogu
        log_success(f"Rozpakowano: {zip_filename}")
        return True
    except zipfile.BadZipFile as e:
        log_error(f"Błąd podczas rozpakowywania pliku ZIP: {e}")
        return False


def delete_old_versions(current_version):
    """Usuwa starsze wersje programu z folderu."""
    config_manager = ConfigManager()
    config = config_manager.config  # Użycie config_manager
    for file in os.listdir():
        if file.startswith("SocialFlow") and file.endswith(".exe") and current_version not in file:
            try:
                os.remove(file)
                log_info(f"Usunięto starą wersję: {file}")
                reset_changelog_viewed()
            except Exception as e:
                log_error(f"Nie udało się usunąć pliku {file}: {e}")


async def check_for_updates(local_version):
    """Sprawdza, czy dostępna jest nowa wersja, i aktualizuje program."""
    latest_version = get_latest_version()  # Przenieś tu, aby przypisać wersję przed usunięciem starych

    if latest_version:
        if latest_version != local_version:
            log_info(f"Wykryto nową wersję: {latest_version}. Aktualizacja...")

            link = get_download_link_with_chromedriver()
            zip_file = download_new_version(link)

            if zip_file and unzip_file(zip_file):
                log_success("Uruchamianie nowej wersji programu...")
                time.sleep(2)  # Krótki czas na zamknięcie bieżącego procesu

                # Ustal nazwę pliku EXE z rozpakowanego archiwum
                exe_file = f"SocialFlow {latest_version}.exe"
                if os.path.exists(exe_file):
                    log_success(f"Uruchomiono {exe_file}")
                    subprocess.Popen(f'cmd /c "cls"', shell=True)
                    subprocess.Popen(exe_file, shell=True)
                else:
                    log_error("Nie znaleziono pliku EXE po rozpakowaniu.")

                os.remove(zip_file)  # Usunięcie pliku ZIP
                os._exit(0)  # Zamknij aktualny proces
            else:
                log_error("Nie udało się pobrać lub rozpakować nowej wersji.")
        else:
            delete_old_versions(latest_version)
            log_success("Wersja programu aktualna.")
    else:
        log_error("Nie udało się pobrać najnowszej wersji.")