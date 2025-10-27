"""Create the initial SYSADMIN user for the Liberty Place HOA platform.

Run: `python backend/manage_create_admin.py --email admin@example.com --password changeme`
"""

import argparse
from contextlib import contextmanager

from backend.auth.jwt import get_password_hash
from backend.config import SessionLocal
from backend.constants import DEFAULT_ROLES
from backend.models.models import Role, User


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_roles(db):
    for name, description in DEFAULT_ROLES:
        role = db.query(Role).filter(Role.name == name).first()
        if not role:
            role = Role(name=name, description=description)
            db.add(role)
    db.flush()


def main():
    parser = argparse.ArgumentParser(description="Create the initial SYSADMIN user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", default="Initial Administrator")
    args = parser.parse_args()

    with session_scope() as db:
        ensure_roles(db)
        sysadmin_role = db.query(Role).filter(Role.name == "SYSADMIN").one()

        existing_user = db.query(User).filter(User.email == args.email).first()
        if existing_user:
            print("User already exists with that email.")
            return

        hashed_password = get_password_hash(args.password)
        user = User(
            email=args.email,
            full_name=args.full_name,
            hashed_password=hashed_password,
            role_id=sysadmin_role.id,
        )
        db.add(user)
        db.flush()
        print(f"Created SYSADMIN user with id {user.id}")


if __name__ == "__main__":
    main()
