import base64
from cryptography.fernet import Fernet
from app.config import settings


def _get_fernet() -> Fernet:
    key = settings.encryption_key.encode()[:32].ljust(32, b'\0')
    encoded_key = base64.urlsafe_b64encode(key)
    return Fernet(encoded_key)


def encrypt_token(token: str) -> str:
    f = _get_fernet()
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()
