"""Set the demo accounts' password hashes from DEMO_PASSWORD.

    python -m app.auth.demo_accounts
    docker compose run --rm backend uv run python -m app.auth.demo_accounts

Runs on every container start after `alembic upgrade head` (backend/start.sh). Without
DEMO_PASSWORD the hashes are cleared and demo login is disabled. A changed or cleared
password also ends the account's existing sessions. Database errors are logged and never
stop the application from starting.
"""

import logging
import sys
from collections.abc import Sequence

from sqlalchemy import Engine, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from app.auth.models import User, UserSession
from app.auth.passwords import hash_password, verify_password
from app.db import get_engine
from app.settings import get_settings

logger = logging.getLogger(__name__)

DEMO_USERNAMES = ("sales", "supervisor")


def sync_demo_passwords(
    engine: Engine, password: str | None, usernames: Sequence[str] = DEMO_USERNAMES
) -> None:
    """Make each listed account's hash match `password` (NULL when None).

    A hash that already verifies is left unchanged; a missing account is skipped. When a
    hash changes or is cleared, the account's sessions are deleted in the same transaction.
    """
    with Session(engine) as session:
        users = session.exec(select(User).where(col(User.username).in_(usernames))).all()
        for user in users:
            if password is None:
                if user.password_hash is None:
                    continue
                user.password_hash = None
                logger.info("Cleared the password of demo account %s", user.username)
            elif not verify_password(password, user.password_hash):
                user.password_hash = hash_password(password)
                logger.info("Set the password of demo account %s", user.username)
            else:
                continue
            session.add(user)
            session.exec(delete(UserSession).where(col(UserSession.user_id) == user.id))
        session.commit()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    secret = get_settings().demo_password
    password = secret.get_secret_value() if secret is not None else None
    if password is None:
        logger.error("DEMO_PASSWORD is not set; login to the demo accounts is disabled.")
    try:
        sync_demo_passwords(get_engine(), password)
    except SQLAlchemyError:
        logger.exception("Could not sync the demo account passwords; continuing without it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
