"""The one place that hashes and verifies passwords (Argon2id via pwdlib)."""

import threading

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher

# OWASP minimum for Argon2id (19 MiB, 2 iterations, 1 lane), small enough for a free
# instance. Each hash stores its own parameters, so older hashes still verify.
_password_hash = PasswordHash((Argon2Hasher(memory_cost=19_456, time_cost=2, parallelism=1),))

# At most this many logins verify a password at once; a login that cannot get a slot
# within LOGIN_VERIFY_WAIT_SECONDS is answered 503, so a burst of parallel logins cannot
# exhaust the memory or CPU of a small instance. Startup sync does not use it.
LOGIN_VERIFY_SLOTS = threading.BoundedSemaphore(2)
LOGIN_VERIFY_WAIT_SECONDS = 2.0

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
