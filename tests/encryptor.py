from cryptography.fernet import Fernet

# Wygeneruj klucz
key = "r-tyOCIy_Y1CHVqcEqL5qZPxqOcbYQ_2qjI5Gc0B8YE="
cipher = Fernet(key)

# Link do pliku
url = "SocialFlow001a@tutanota.com:PXASrQRxA=5E"

# Szyfrowanie linku
encrypted_url = cipher.encrypt(url.encode())
print(f"Szyfrowany link: {encrypted_url.decode()}")
#print(f"Klucz: {key.decode()}")

input()
