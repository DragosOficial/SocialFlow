import os
import json
import platform
import logging
import sys

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)

def create_firebase_key():
    """
    Tworzy dane klucza Firebase Admin SDK.
    """
    return {
        "type": "service_account",
        "project_id": "socialflow-2f45d",
        "private_key_id": "d3f4ae49f7b67d712398e61b3035834ef14fb3ef",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDfmNvAvItLgLPW\n09V8g51tVjLLiotSa2c1fLIIVE4XX6HWRgfUeN6F+6i1Ra0Psxc4HQBJr6yaKiNJ\nD2PdKQPGylYmbSksTHTjdFBLmSOGCa0tMjiaHlHSHDbUmr/wsNoD6HO+kcBImVZt\nuZXrJRWhX52R7PFz8W78XLCEKy4PCrYTBpmrFyySoBPWlMfpQsdihFBOSJzu9Ya0\nLATL+0z6m6tQMyT1E3LTzi0FGvX2Y0JxzdUAs6snHTcjArRdecLtWquk8dRmQt4N\n08q15KezuUi/CNzBw1urdTGghZAdcujYbo6239j+/MvxpOn1vTf2tS/GeHxta7ZD\nVcRHb/cRAgMBAAECggEADOGR+1sBTVK3SY9/k4JDjfpyx64OE6vzUK4D1Z4Bt6//\nM0hqiA+EhkR2tiay7x4antVw4E3aDDGUQc+8qY+E061xZBpSzmYDL91SCODkHoMt\nMlbb0ukfPpL4h6v4lcWicaoxDM/5u1T2GTEhVWAYDGllOvRi/pJwmeI/GwYfy6bv\nMy5Q1LVb1EJYwfIe2/d/O9HXMQMGYBD0PGi3FKMxr7lCOHwV/Ukz3ZdF/NfHWlY9\nquvjQUzLY128oWUh0o54CGwTdTOVWEzekCvGirugo0USQKcASdm7OU49w9GaCJcq\n7CwRXlXe9jrtA/qO0sh+X6HZfl8pe7XUHdP2pchn7wKBgQD+UZlTj2fSZrShmpya\nTcixI8Nedmg5xQ5zQg3cF+U+g5zVMjbflJOJrMj4gtBm1QXvpzd2pmgTGvSQnCyY\nKhHIcjqHLYhWx/V42ArnjeXWD0SLDE/HC8/VzBNYDAACAtYKU18E3mnkSxQjqVIo\n5vE0h6NBOUU5tLDvWJdl1OT2bwKBgQDhE0Ri49WO4eXikXsFsqRq+wt2WGvWU0aP\nRJ+ibKsSO84N1jnxIx9hFKK2UJsH87mbQ7fi7w6xFzyNOe1RnmrjVS5Sa3m6G90e\nWbuMkWM/bTbVPtN3FvIgvPB5ZNRa7n3Y5xu08UuXU96sW3kt7jHhdGlbziW+RaRy\nYv3NfwyqfwKBgQDJhCr0VVu1EoDq1LJmamAuTOJQBY8Mx6JtndeRoLWb1Xn+TS3B\n9974ZptQn4c3FHEBtwRx1eX9zYwg0j9by2oP5MOPvXqdGRDfUoFBfeSyu6Jac8T7\nOdbT2EMzrz6KWWj1AZ73Iq3RodQxdceOdYCHWTr5QcIiuZTB8vb0T7+lrQKBgQCG\nUsFVYzNoelh/xuLsm5iUYA6PKmXxGvHZPtMmVEQkNZzblSYvSw7HGVGiDKj5LfNv\nPhLYVGMoPP3eKtv/AdQ4p/VlKs8Syt5D5rmPQpVAnSVETqJVSFRoRVoemJZDTmG8\nuPBIJFlAjsUth8niJ22NZ7QZHgZYb6ecvIdLxK8CcQKBgQDxAjM8VaKj3pd8FoMR\nco3L4HWTo5H7bB3CSYYG60RNQxs5QSPLWN9s1uUKXEU1axyZZe6TFChhXemr4gxM\nRvPS/BcmSqGqgxlWbKR5pH4vKajXMtv0O43e8QHGfNTpWA1tzGhWvtt1rRGn8FRp\nYWxROjO6OnB4IDg2ormxDqnP3A==\n-----END PRIVATE KEY-----\n",
        "client_email": "firebase-adminsdk-hf73n@socialflow-2f45d.iam.gserviceaccount.com",
        "client_id": "115365989004021763032",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-hf73n%40socialflow-2f45d.iam.gserviceaccount.com",
        "universe_domain": "googleapis.com"
    }


def get_hidden_dir():
    """
    Zwraca ścieżkę do ukrytego katalogu, zależnie od systemu operacyjnego.
    """
    system = platform.system().lower()

    if system == "windows":
        return os.path.join(os.getenv("APPDATA"), "FirebaseAdmin")
    elif system == "darwin":  # macOS
        return os.path.join(os.path.expanduser("~"), ".firebase_admin")
    else:  # Linux
        return os.path.join(os.path.expanduser("~"), ".firebase_admin")

def save_firebase_key_to_file(firebase_key, dir_path):
    """
    Zapisuje dane klucza Firebase do pliku JSON.
    """
    json_file_path = os.path.join(dir_path, "firebase_admin_key.json")
    
    if not os.path.exists(json_file_path):
        with open(json_file_path, "w") as json_file:
            json.dump(firebase_key, json_file, indent=4)
        #logging.info(f"Plik klucza zapisano w {json_file_path}")
    #else:
        #logging.warning(f"Plik {json_file_path} już istnieje, nie zapisano nowego pliku.")
    
    return json_file_path

def set_firebase_key_env(json_file_path):
    """
    Ustawia zmienną środowiskową wskazującą na ścieżkę pliku JSON z danymi Firebase.
    """
    system = platform.system().lower()
    
    if system == "windows":
        command = f'setx FIREBASE_ADMIN_KEY_PATH "{json_file_path}"'
    elif system == "darwin" or system == "linux":
        command = f'export FIREBASE_ADMIN_KEY_PATH="{json_file_path}"'
    else:
        raise OSError(f"Nieobsługiwany system operacyjny: {system}")
    
    os.system(command)
    #logging.info("Zmienne środowiskowe zostały ustawione.")

def setup_firebase_admin_key():
    """
    Kompletny proces konfiguracji klucza Firebase Admin SDK.
    """
    try:
        # Tworzymy dane klucza Firebase
        firebase_key = create_firebase_key()

        # Sprawdzamy, czy katalog istnieje, jeśli nie, tworzymy go
        hidden_dir = get_hidden_dir()
        os.makedirs(hidden_dir, exist_ok=True)

        # Zapisujemy klucz do pliku
        json_file_path = save_firebase_key_to_file(firebase_key, hidden_dir)

        # Ustawiamy zmienną środowiskową
        set_firebase_key_env(json_file_path)

        admin_key = os.getenv("FIREBASE_ADMIN_KEY_PATH")
        print(admin_key)
    except Exception as e:
        logging.error(f"Błąd podczas konfiguracji: {e}")

if __name__ == "__main__":
    setup_firebase_admin_key()