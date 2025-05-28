from cryptography.fernet import Fernet

# Klucz do deszyfrowania
key = "r-tyOCIy_Y1CHVqcEqL5qZPxqOcbYQ_2qjI5Gc0B8YE=".encode()  # Konwersja klucza do bajtów
cipher = Fernet(key)

# Zaszyfrowany tekst
encrypted_message = b"gAAAAABnI2DS_Dcih-fCU4jh74rusTFyUlVYALsKsls4QPhgqb0W18v_3dcN3vRdgCvc0xkG9ckwjZDevdSxUw1L2Le3RlLd-J0JPqoLtDK5YnpmrK3cd-WO9h4yoRZTh_b2TOrxjnhP"

# Deszyfrowanie wiadomości
try:
    decrypted_message = cipher.decrypt(encrypted_message)
    print("Odszyfrowana wiadomość:", decrypted_message.decode())
except Exception as e:
    print("Błąd deszyfrowania:", str(e))

input()