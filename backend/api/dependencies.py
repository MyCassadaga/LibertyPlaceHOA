from typing import Generator, Optional

from fastapi import Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..auth.jwt import get_current_user
from ..config import SessionLocal
from ..models.models import Owner, User


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_owner_for_user(db: Session, user: User) -> Optional[Owner]:
    if not user.email:
        return None
    email = user.email.lower()
    return (
        db.query(Owner)
        .filter(
            or_(
                func.lower(Owner.primary_email) == email,
                func.lower(Owner.secondary_email) == email,
            )
        )
        .first()
    )


def require_owner_record(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Owner:
    owner = get_owner_for_user(db, user)
    if not owner:
        raise HTTPException(status_code=404, detail="Linked owner record not found")
    return owner
