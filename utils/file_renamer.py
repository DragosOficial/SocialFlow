import os
import sys
from utils.utils import log_success, log_error
import subprocess


async def ensure_correct_filename(local_version):
    """Sprawdza, czy nazwa programu jest zgodna z formatem 'SocialFlow {wersja programu}.exe'. 
    Jeśli nie, zmienia nazwę pliku na poprawną i uruchamia go ponownie."""

    correct_filename = f"SocialFlow {local_version}.exe"
    # Użycie sys.argv[0] dla poprawnej ścieżki
    current_filename = os.path.basename(sys.argv[0])

    # Sprawdzamy, czy bieżąca nazwa pliku jest poprawna
    if current_filename != correct_filename:
        log_error("Nazwa programu jest niepoprawna.")
        try:
            # Zmiana nazwy pliku na poprawną
            new_filepath = os.path.join(
                os.path.dirname(sys.argv[0]), correct_filename)
            os.rename(sys.argv[0], new_filepath)
            log_success(f"Nazwa programu została zmieniona na: {correct_filename}")

            # Ponowne uruchomienie programu z nową nazwą
            subprocess.Popen([new_filepath], shell=True)
            sys.exit(0)  # Zamyka bieżący proces, by pozostał tylko nowy

        except FileNotFoundError:
            log_error("Nie znaleziono pliku do zmiany nazwy.")
        except Exception as e:
            log_error(f"Błąd podczas zmiany nazwy programu: {e}")
    else:
        log_success("Nazwa pliku jest już zgodna z wymaganym formatem.")
