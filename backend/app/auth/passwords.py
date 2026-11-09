"""The one place that hashes and verifies passwords (Argon2 via pwdlib)."""

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_password_hash = PasswordHash.recommended()

# Verified against when there is no real hash (unknown login, account without a
# password), so the response time does not reveal whether the account exists.
_DUMMY_HASH = _password_hash.hash("dummy-password-for-constant-time")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """True only when `password` matches `password_hash`; None always gives False."""
    if password_hash is None:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    try:
        return _password_hash.verify(password, password_hash)
    except UnknownHashError:
        # A value that is not a recognized hash can never match.
        return False
