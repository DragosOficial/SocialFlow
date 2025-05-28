import os
import json
import time
import shutil
import traceback
from typing import Any, Dict
from jsonschema import Draft7Validator
import asyncio
import aiofiles
from utils.utils import log_info, log_error, log_warning

LOCAL_VERSION: str = "1.0.0-alpha"
CONFIG_FILE_PATH: str = "config.json"
CONFIG_BACKUP_PATH: str = "config.json.bak"

MAX_RETRIES: int = 3
RETRY_DELAY: float = 0.5 

# Prekompilowany schemat JSON dla konfiguracji
CONFIG_VALIDATOR = Draft7Validator({
    "type": "object",
    "properties": {
        "local_version": {"type": "string"},
        "changelog_viewed": {"type": "boolean"}
    },
    "required": ["local_version", "changelog_viewed"],
    "additionalProperties": True
})


class ConfigManager:
    _instance = None

    def __new__(cls, *args, **kwargs) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Inicjalizuje ConfigManager z wersją aplikacji."""
        if not hasattr(self, "initialized"):
            self.initialized: bool = True
            self.app_version: str = LOCAL_VERSION
            # Lazy loading – konfiguracja zostanie wczytana przy pierwszym odwołaniu
            self._config: Dict[str, Any] = None
            self._last_mod_time: float = 0.0

    @property
    def config(self) -> Dict[str, Any]:
        """Właściwość udostępniająca konfigurację, z mechanizmem lazy loading i cache’owaniem."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _create_default_config(self) -> Dict[str, Any]:
        """Tworzy domyślną konfigurację."""
        return {
            "local_version": self.app_version,
            "changelog_viewed": False
        }

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Waliduje strukturę wczytanej konfiguracji przy użyciu prekompilowanego schematu.
        Zwraca True, jeśli konfiguracja jest poprawna, w przeciwnym razie loguje błędy i zwraca False.
        """
        errors = sorted(CONFIG_VALIDATOR.iter_errors(config), key=lambda e: e.path)
        if errors:
            #for error in errors:
                #log_error(f"Walidacja schematu konfiguracji nie powiodła się: {error.message}")
            return False

        # Dodatkowa walidacja – sprawdzenie obecności wszystkich wymaganych pól
        default_config = self._create_default_config()
        for key in default_config.keys():
            if key not in config:
                log_warning(f"Brakujący klucz w konfiguracji: {key}")
                return False
        return True

    def _migrate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migruje konfigurację do bieżącej wersji. Jeśli wersja konfiguracji jest starsza,
        dodaje nowe pola z domyślnymi wartościami, nie naruszając istniejących ustawień.
        """
        if config.get("local_version") != self.app_version:
            log_warning("Wersja konfiguracji jest starsza niż wersja aplikacji. Migracja...")
            default_config = self._create_default_config()
            for key, default_value in default_config.items():
                if key not in config:
                    log_info(f"Dodawanie nowego pola w migracji: {key} = {default_value}")
                    config[key] = default_value
            config["local_version"] = self.app_version
        return config

    def _update_missing_fields(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uzupełnia brakujące pola w konfiguracji.
        """
        default_config = self._create_default_config()
        for key, value in default_config.items():
            if key not in config:
                log_info(f"Uzupełnianie brakującego pola: {key}")
                config[key] = value
        return config

    def _update_config_if_needed(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sprawdza wersję konfiguracji, waliduje jej strukturę oraz uzupełnia brakujące pola.
        Jeśli wykryje zmiany, zapisuje zaktualizowaną konfigurację do pliku.
        """
        updated: bool = False

        if not self._validate_config(config):
            log_info("Konfiguracja nie przeszła walidacji. Uzupełniam brakujące pola.")
            config = self._update_missing_fields(config)
            updated = True

        migrated_config = self._migrate_config(config)
        if migrated_config != config:
            updated = True
            config = migrated_config

        if updated:
            log_info("Konfiguracja została zaktualizowana. Zapisuję zmiany do pliku.")
            self.save_config(config)

        return config

    def _load_config(self) -> Dict[str, Any]:
        """
        Ładuje konfigurację z pliku lub tworzy domyślną. Wykorzystuje mechanizm cache’owania –
        jeśli plik nie uległ zmianie, zwraca wcześniej wczytaną konfigurację.
        """
        start_time = time.time()
        if os.path.exists(CONFIG_FILE_PATH):
            current_mod_time = os.path.getmtime(CONFIG_FILE_PATH)
            if current_mod_time == self._last_mod_time and self._config is not None:
                log_info("Wczytano konfigurację z cache.")
                return self._config
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    with open(CONFIG_FILE_PATH, "r") as file:
                        config = json.load(file)
                    if not self._validate_config(config):
                        log_warning("Odczytana konfiguracja jest niekompletna lub uszkodzona.")
                    config = self._update_config_if_needed(config)
                    self._last_mod_time = os.path.getmtime(CONFIG_FILE_PATH)
                    log_info(f"Konfiguracja wczytana w {time.time() - start_time:.3f} sekund.")
                    return config
                except FileNotFoundError as fnf_error:
                    log_error(f"Plik konfiguracyjny nie został znaleziony: {fnf_error}")
                    break
                except json.JSONDecodeError as json_error:
                    log_error(f"Błąd podczas wczytywania konfiguracji (JSON): {json_error}")
                    log_error(traceback.format_exc())
                    break
                except IOError as io_error:
                    log_error(f"Błąd I/O przy próbie wczytania konfiguracji (próba {attempt}): {io_error}")
                    log_error(traceback.format_exc())
                    time.sleep(RETRY_DELAY)
                except Exception as e:
                    log_error(f"Nieoczekiwany błąd podczas wczytywania konfiguracji (próba {attempt}): {e}")
                    log_error(traceback.format_exc())
                    time.sleep(RETRY_DELAY)

        log_warning("Plik konfiguracyjny nie istnieje lub jest uszkodzony. Tworzenie nowej konfiguracji.")
        default_config = self._create_default_config()
        self.save_config(default_config)
        return default_config

    async def _async_load_config(self) -> Dict[str, Any]:
        """
        Asynchroniczna wersja metody ładowania konfiguracji.
        """
        start_time = time.time()
        if os.path.exists(CONFIG_FILE_PATH):
            current_mod_time = os.path.getmtime(CONFIG_FILE_PATH)
            if current_mod_time == self._last_mod_time and self._config is not None:
                log_info("Wczytano konfigurację z cache (async).")
                return self._config
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    async with aiofiles.open(CONFIG_FILE_PATH, "r") as file:
                        data = await file.read()
                        config = json.loads(data)
                    if not self._validate_config(config):
                        log_warning("Odczytana konfiguracja jest niekompletna lub uszkodzona (async).")
                    config = self._update_config_if_needed(config)
                    self._last_mod_time = os.path.getmtime(CONFIG_FILE_PATH)
                    log_info(f"Konfiguracja wczytana asynchronicznie w {time.time() - start_time:.3f} sekund.")
                    return config
                except FileNotFoundError as fnf_error:
                    log_error(f"Plik konfiguracyjny nie został znaleziony (async): {fnf_error}")
                    break
                except json.JSONDecodeError as json_error:
                    log_error(f"Błąd podczas wczytywania konfiguracji (JSON, async): {json_error}")
                    log_error(traceback.format_exc())
                    break
                except IOError as io_error:
                    log_error(f"Błąd I/O przy próbie wczytania konfiguracji (async, próba {attempt}): {io_error}")
                    log_error(traceback.format_exc())
                    await asyncio.sleep(RETRY_DELAY)
                except Exception as e:
                    log_error(f"Nieoczekiwany błąd podczas wczytywania konfiguracji (async, próba {attempt}): {e}")
                    log_error(traceback.format_exc())
                    await asyncio.sleep(RETRY_DELAY)
        log_warning("Plik konfiguracyjny nie istnieje lub jest uszkodzony (async). Tworzenie nowej konfiguracji.")
        default_config = self._create_default_config()
        await self.async_save_config(default_config)
        return default_config

    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Zapisuje konfigurację do pliku JSON.
        Przed zapisem waliduje integralność danych, tworzy backup tylko, gdy plik został zmodyfikowany,
        oraz monitoruje czas wykonania operacji.
        """
        start_time = time.time()
        if not self._validate_config(config):
            log_error("Konfiguracja nie przeszła walidacji przed zapisem. Zapis przerwany.")
            return

        if os.path.exists(CONFIG_FILE_PATH):
            try:
                current_mod_time = os.path.getmtime(CONFIG_FILE_PATH)
                if current_mod_time != self._last_mod_time:
                    shutil.copy2(CONFIG_FILE_PATH, CONFIG_BACKUP_PATH)
                    log_info(f"Backup konfiguracji został utworzony: {CONFIG_BACKUP_PATH}")
            except Exception as backup_error:
                log_error(f"Błąd przy tworzeniu backupu konfiguracji: {backup_error}")
                log_error(traceback.format_exc())

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with open(CONFIG_FILE_PATH, "w") as file:
                    json.dump(config, file, indent=4)
                self._last_mod_time = os.path.getmtime(CONFIG_FILE_PATH)
                log_info(f"Konfiguracja została pomyślnie zapisana w {time.time() - start_time:.3f} sekund.")
                self._config = config  # Aktualizacja cache
                return
            except IOError as io_error:
                log_error(f"Błąd I/O podczas zapisywania konfiguracji (próba {attempt}): {io_error}")
                log_error(traceback.format_exc())
                time.sleep(RETRY_DELAY)
            except Exception as e:
                log_error(f"Nieoczekiwany błąd podczas zapisywania konfiguracji (próba {attempt}): {e}")
                log_error(traceback.format_exc())
                time.sleep(RETRY_DELAY)
        log_error("Nie udało się zapisać konfiguracji po wielu próbach. Operacja zapisu przerwana.")

    async def async_save_config(self, config: Dict[str, Any]) -> None:
        """
        Asynchroniczna wersja metody zapisu konfiguracji.
        """
        start_time = time.time()
        if not self._validate_config(config):
            log_error("Konfiguracja nie przeszła walidacji przed zapisem (async). Zapis przerwany.")
            return

        if os.path.exists(CONFIG_FILE_PATH):
            try:
                current_mod_time = os.path.getmtime(CONFIG_FILE_PATH)
                if current_mod_time != self._last_mod_time:
                    shutil.copy2(CONFIG_FILE_PATH, CONFIG_BACKUP_PATH)
                    log_info(f"Backup konfiguracji został utworzony (async): {CONFIG_BACKUP_PATH}")
            except Exception as backup_error:
                log_error(f"Błąd przy tworzeniu backupu konfiguracji (async): {backup_error}")
                log_error(traceback.format_exc())

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with aiofiles.open(CONFIG_FILE_PATH, "w") as file:
                    data = json.dumps(config, indent=4)
                    await file.write(data)
                self._last_mod_time = os.path.getmtime(CONFIG_FILE_PATH)
                log_info(f"Konfiguracja została pomyślnie zapisana asynchronicznie w {time.time() - start_time:.3f} sekund.")
                self._config = config  # Aktualizacja cache
                return
            except IOError as io_error:
                log_error(f"Błąd I/O podczas zapisywania konfiguracji (async, próba {attempt}): {io_error}")
                log_error(traceback.format_exc())
                await asyncio.sleep(RETRY_DELAY)
            except Exception as e:
                log_error(f"Nieoczekiwany błąd podczas zapisywania konfiguracji (async, próba {attempt}): {e}")
                log_error(traceback.format_exc())
                await asyncio.sleep(RETRY_DELAY)
        log_error("Nie udało się zapisać konfiguracji asynchronicznie po wielu próbach. Operacja zapisu przerwana.")

    def reload_config(self) -> None:
        """
        Dynamicznie przeładowuje konfigurację z pliku.
        Aktualizuje wewnętrzny stan obiektu ConfigManager bez konieczności restartu aplikacji.
        """
        log_info("Dynamiczne przeładowanie konfiguracji...")
        self._config = self._load_config()
        log_info("Konfiguracja została przeładowana.")