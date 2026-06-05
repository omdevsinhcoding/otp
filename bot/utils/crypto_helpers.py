import os
from cryptography.fernet import Fernet

_key = os.getenv("ENCRYPTION_KEY")
if not _key:
    # Fallback key mapping if none provided (ONLY FOR DEV!)
    _key = Fernet.generate_key().decode('utf-8')
    os.environ["ENCRYPTION_KEY"] = _key

cipher_suite = Fernet(_key.encode('utf-8'))

def encrypt_token(token: str) -> str:
    """Encrypts a bot token before storing in DB."""
    return cipher_suite.encrypt(token.encode('utf-8')).decode('utf-8')

def decrypt_token(encrypted_token: str) -> str:
    """Decrypts a bot token from DB."""
    return cipher_suite.decrypt(encrypted_token.encode('utf-8')).decode('utf-8')
