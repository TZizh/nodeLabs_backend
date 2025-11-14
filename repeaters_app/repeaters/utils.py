
import hashlib, os

def hash_new_api_key(plaintext: str):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', plaintext.encode('utf-8'), salt, 120000, dklen=32)
    return salt.hex(), dk.hex()
