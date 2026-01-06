from typing import Generator, List, Optional

from fastapi import Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..auth.jwt import get_current_user
from ..config import SessionLocal
from ..models.models import Owner, OwnerUserLink, User


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_owners_for_user(db: Session, user: User) -> List[Owner]:
    linked_owners = (
        db.query(Owner)
        .join(OwnerUserLink, OwnerUserLink.owner_id == Owner.id)
        .filter(OwnerUserLink.user_id == user.id)
        .filter(Owner.is_archived.is_(False))
        .order_by(OwnerUserLink.created_at.asc())
        .all()
    )
    if linked_owners:
        return linked_owners
    if not user.email:
        return []
    email = user.email.lower()
    return (
        db.query(Owner)
        .filter(
            or_(
                func.lower(Owner.primary_email) == email,
                func.lower(Owner.secondary_email) == email,
            )
        )
        .filter(Owner.is_archived.is_(False))
        .order_by(Owner.property_address.asc())
        .all()
    )


def get_owner_for_user(db: Session, user: User) -> Optional[Owner]:
    owners = get_owners_for_user(db, user)
    if owners:
        return owners[0]
    return None


def require_owner_record(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Owner:
    owner = get_owner_for_user(db, user)
    if not owner:
        raise HTTPException(status_code=404, detail="Linked owner record not found")
    return owner
