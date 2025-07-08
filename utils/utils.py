import os
import logging
import sys
import GPUtil
import platform
import subprocess
import re
from google.cloud import storage
from google.cloud import firestore
from firebase_admin import credentials, firestore, initialize_app, storage
from colorama import init, Fore, Style
from datetime import datetime

init(autoreset=True)

LOG_FILE = "logs.txt"

cred = credentials.Certificate(os.getenv("FIREBASE_ADMIN_KEY_PATH"))
firebase_app = initialize_app(cred, {
    'storageBucket': 'socialflow-2f45d.firebasestorage.app'
})
db = firestore.client()
storage_bucket = storage.bucket()

ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# Ustawienie logowania
logging.basicConfig(
    level=logging.ERROR,  # W zależności od poziomu, np. DEBUG, INFO, ERROR
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),  # Zapis do pliku
        logging.StreamHandler(sys.stdout)  # Zapis do konsoli
    ]
)

def clear_console():
    os.system("cls" if os.name == "nt" else "clear")


def strip_ansi_codes(text: str) -> str:
    """Usuwa sekwencje ANSI (kolory itp.) z tekstu."""
    return ansi_escape.sub('', text)


def log_message(prefix, message, is_logging=True):
    """Displays a message with a prefix in the console and logs it to a file (bez kolorów)."""
    plain_prefix = strip_ansi_codes(prefix)  # bez kolorów
    formatted_message = f"{prefix} {message}"            # kolorowe na konsolę
    plain_message = f"{plain_prefix} {message}"          # czysty tekst do pliku

    print(formatted_message)
    if is_logging:
        log_to_file(plain_message)

def log_success(message):
    """Displays a success message in green and logs it."""
    log_message(f"{Fore.GREEN}[+]{Style.RESET_ALL}", message)

def log_error(message):
    """Displays an error message in red and logs it."""
    log_message(f"{Fore.RED}[-]{Style.RESET_ALL}", message)

def log_info(message):
    """Displays an info message in blue and logs it."""
    log_message(f"{Fore.BLUE}[!]{Style.RESET_ALL}", message)

def log_warning(message):
    """Displays a warning message in yellow and logs it."""
    log_message(f"{Fore.YELLOW}[!]{Style.RESET_ALL}", message)

def log_debug(message):
    """Displays a debug message in purple and logs it."""
    log_message(f"{Fore.MAGENTA}[D]{Style.RESET_ALL}", message)

def start_new_session(version):
    """Logs the start of a new session with date, time, and version."""
    separator = "=" * 50
    session_start = f"\n{separator}\nNowa Sesja - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nWersja: {version}\n{separator}\n"
    log_to_file(session_start)  # Loguje do pliku, bez wyświetlania w konsoli

def log_to_file(message):
    """Writes a message to the log file."""
    with open(LOG_FILE, "a") as log_file:
        log_file.write(message + "\n")

# Globalne przechwytywanie wyjątków
def handle_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    # Logowanie błędu do pliku i konsoli
    logging.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
    print(f"{Fore.RED}[ERROR] Unexpected error occurred. See log for details.{Style.RESET_ALL}")

def get_hardware_info() -> str:
    """Zwraca informacje o sprzęcie (procesor, karta graficzna)."""
    
    # Pobranie nazwy procesora w bardziej czytelnej formie
    cpu_info = get_processor_name()

    # Pobranie informacji o GPU
    gpus = GPUtil.getGPUs()
    if gpus:
        gpu_info = gpus[0].name  # Dedykowana karta GPU
    else:
        # Próba pobrania informacji o zintegrowanej karcie
        gpu_info = get_integrated_gpu()

    return f"{cpu_info} | {gpu_info}"

def get_processor_name():
    system = platform.system()
    try:
        if system == "Windows":
            # W systemie Windows używamy polecenia 'wmic'
            output = subprocess.check_output("wmic cpu get Name", shell=True)
            return output.decode().split("\n")[1].strip()
        elif system == "Linux":
            # W systemie Linux odczytujemy plik /proc/cpuinfo
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[1].strip()
        elif system == "Darwin":
            # W systemie macOS używamy polecenia 'sysctl'
            output = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"])
            return output.decode().strip()
        else:
            return "Nieznany system operacyjny"
    except Exception as e:
        return f"Błąd podczas pobierania nazwy procesora: {e}"
    
def get_integrated_gpu() -> str:
    """Próbuje pobrać informacje o zintegrowanej karcie graficznej."""
    try:
        if platform.system() == "Windows":
            output = subprocess.check_output("wmic path win32_VideoController get Name", shell=True).decode()
            gpus = [line.strip() for line in output.split("\n") if line.strip() and "Name" not in line]
            return gpus[0] if gpus else "Brak informacji o GPU"
        elif platform.system() == "Linux":
            output = subprocess.check_output("lspci | grep -i 'vga\\|3d\\|display'", shell=True).decode()
            return output.split("\n")[0] if output else "Brak informacji o GPU"
    except Exception:
        return "Brak informacji o GPU"

# Ustawienie globalnego handlera wyjątków
sys.excepthook = handle_exception