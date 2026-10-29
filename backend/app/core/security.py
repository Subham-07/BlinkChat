"""Password hashing (Argon2id) and session token generation."""
import secrets
import hashlib
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Return an Argon2id hash of the password."""
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if the password matches the hash."""
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_room_code(length: int = 8) -> str:
    """Return a cryptographically random URL-safe room code (uppercase alphanumeric)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Unambiguous characters
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_room_password(length: int = 12) -> str:
    """Return a strong random password."""
    # Mix of upper, lower, digits, symbols for readability and strength
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        # Ensure at least one of each category
        has_upper = any(c.isupper() for c in pwd)
        has_lower = any(c.islower() for c in pwd)
        has_digit = any(c.isdigit() for c in pwd)
        has_sym = any(c in "!@#$%" for c in pwd)
        if has_upper and has_lower and has_digit and has_sym:
            return pwd


def generate_session_token() -> str:
    """Return a cryptographically random session token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return a SHA-256 hash of a session token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()
