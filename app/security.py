import hmac
import hashlib, os
import jwt
from datetime import datetime, timedelta
from .config import JWT_SECRET, JWT_EXPIRE_MIN

def hash_password(password: str, salt: bytes|None=None) -> str:
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return salt.hex() + ":" + dk.hex()

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return hmac.compare_digest(dk, expected)

    except Exception:
        return False

def create_token(user_id: int, role: str, clinic_id: int|None) -> str:
    now = datetime.utcnow()
    payload = {"sub": str(user_id), "role": role, "clinic_id": clinic_id,
               "iat": int(now.timestamp()),
               "exp": int((now + timedelta(minutes=JWT_EXPIRE_MIN)).timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
