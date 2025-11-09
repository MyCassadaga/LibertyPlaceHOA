#!/usr/bin/env python
"""
Seed script to populate the database with sample data for local development.

Usage:
    python scripts/seed_data.py --homeowners 5
"""

import argparse
from datetime import date, timedelta
from decimal import Decimal
from typing import List

from backend.auth.jwt import get_password_hash
from backend.config import SessionLocal
from backend.main import ensure_billing_policy, ensure_default_roles, ensure_user_role_links
from backend.models.models import (
    Invoice,
    Owner,
    OwnerUserLink,
    Role,
    User,
)


def get_role(session, name: str) -> Role:
    role = session.query(Role).filter(Role.name == name).first()
    if not role:
        raise RuntimeError(f"Role '{name}' is not defined. Run ensure_default_roles first.")
    return role


def create_admin_user(session) -> User:
    admin = session.query(User).filter(User.email == "admin@example.com").first()
    if admin:
        return admin

    sysadmin_role = get_role(session, "SYSADMIN")
    board_role = get_role(session, "BOARD")

    admin = User(
        email="admin@example.com",
        full_name="Site Administrator",
        hashed_password=get_password_hash("changeme"),
        is_active=True,
    )
    admin.roles.extend([sysadmin_role, board_role])
    session.add(admin)
    session.flush()
    return admin


def create_homeowner_bundle(session, index: int) -> None:
    homeowner_role = get_role(session, "HOMEOWNER")
    owner = Owner(
        primary_name=f"Test Owner {index}",
        property_address=f"{100 + index} Liberty Way",
        primary_email=f"owner{index}@example.com",
        lot=f"HLOT-{index:03d}",
    )
    session.add(owner)
    session.flush()

    user = User(
        email=owner.primary_email,
        full_name=owner.primary_name,
        hashed_password=get_password_hash("changeme"),
        is_active=True,
    )
    user.roles.append(homeowner_role)
    session.add(user)
    session.flush()

    session.add(OwnerUserLink(owner_id=owner.id, user_id=user.id, link_type="PRIMARY"))

    today = date.today()
    for offset in range(2):
        invoice = Invoice(
            owner_id=owner.id,
            amount=Decimal("150.00"),
            original_amount=Decimal("150.00"),
            due_date=today + timedelta(days=30 * (offset + 1)),
            status="OPEN",
            lot=owner.lot,
        )
        session.add(invoice)


def seed_database(homeowners: int) -> None:
    with SessionLocal() as session:
        ensure_default_roles(session)
        ensure_user_role_links(session)
        ensure_billing_policy(session)

        create_admin_user(session)

        existing = session.query(Owner).count()
        targets = max(homeowners, 0)
        start_index = existing + 1

        for offset in range(targets):
            create_homeowner_bundle(session, start_index + offset)

        session.commit()
        print(f"Seed complete. Created {targets} homeowner accounts (password: 'changeme').")


def main():
    parser = argparse.ArgumentParser(description="Seed the HOA database with sample data.")
    parser.add_argument("--homeowners", type=int, default=5, help="Number of homeowner accounts to create")
    args = parser.parse_args()
    seed_database(args.homeowners)


if __name__ == "__main__":
    main()
