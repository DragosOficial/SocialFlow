import aiohttp
import asyncio
import os
import json
import unidecode
from aiofiles import open as aio_open
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials

FIREBASE_ADMIN_KEY_PATH = os.getenv("FIREBASE_ADMIN_KEY_PATH")
with open(FIREBASE_ADMIN_KEY_PATH, 'r') as key_file:
    admin_key = json.load(key_file)

# Wartości z klucza admin
PRIVATE_KEY = admin_key["private_key"]
PROJECT_ID = admin_key["project_id"]

# Firestore REST API URL
FIRESTORE_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
COLLECTION = "last_names_database"

async def get_existing_names(session):
    """Pobiera istniejące dokumenty z Firestore."""
    url = f"{FIRESTORE_BASE_URL}/{COLLECTION}?key={PRIVATE_KEY}"
    async with session.get(url) as response:
        if response.status == 200:
            data = await response.json()
            return {doc['name'].split("/")[-1]: doc['fields']['count']['integerValue'] for doc in data.get('documents', [])}
        return {}

async def save_name(session, original_name):
    """Zapisuje imię do Firestore."""
    name = unidecode.unidecode(original_name)  # Usuwanie polskich znaków
    url = f"{FIRESTORE_BASE_URL}/{COLLECTION}/{name}?key={PRIVATE_KEY}"
    data = {"fields": {
        "count": {"integerValue": "0"},  # Zawsze ustawione na 0
        "gender": {"stringValue": "male"},  # Dodanie zmiennej płci
        "original_name": {"stringValue": original_name}  # Przechowywanie oryginalnego imienia
    }}
    async with session.patch(url, json=data) as response:
        if response.status == 200:
            print(f"Dodano: {original_name} (liczba: 0, płeć: male)")
        else:
            print(f"Błąd zapisu {original_name}: {await response.text()}")

async def process_names(file_path):
    """Przetwarza plik txt i zapisuje unikalne imiona do Firestore."""
    async with aiohttp.ClientSession() as session:
        async with aio_open(file_path, 'r', encoding='utf-8') as file:
            async for line in file:
                original_name = line.strip()
                if not original_name:
                    continue
                await save_name(session, original_name)

if __name__ == "__main__":
    file_path = input("Podaj ścieżkę do pliku .txt: ")
    if os.path.exists(file_path):
        asyncio.run(process_names(file_path))
    else:
        print("Plik nie istnieje!")