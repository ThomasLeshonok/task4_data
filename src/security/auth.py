import getpass
import hashlib
import hmac
import os
import secrets

DEFAULT_USERNAME = "Customer"
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt:{salt.hex()}:{digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt, digest = stored.split(":")
        if algorithm != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
    except ValueError:
        return False
    return hmac.compare_digest(candidate.hex(), digest)

def password_configured() -> bool:
    return bool(os.environ.get("APP_PASSWORD_HASH"))

def check_credentials(username: str, password: str) -> bool:
    stored = os.environ.get("APP_PASSWORD_HASH", "")
    expected = os.environ.get("APP_USERNAME", DEFAULT_USERNAME)
    user_ok = hmac.compare_digest(username.strip().encode(), expected.encode())
    password_ok = bool(stored) and verify_password(password, stored)
    return user_ok and password_ok


if __name__ == "__main__":
    first = getpass.getpass("New password: ")
    if len(first) < 10:
        raise SystemExit("Use at least 10 characters.")
    if getpass.getpass("Repeat password: ") != first:
        raise SystemExit("Passwords do not match.")
    print(f"APP_PASSWORD_HASH={hash_password(first)}")
