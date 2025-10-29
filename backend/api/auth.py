from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, joinedload

from ..api.dependencies import get_db
from ..auth.jwt import create_access_token, get_current_user, get_password_hash, require_roles, verify_password
from ..models.models import Role, User
from ..schemas.schemas import RoleRead, Token, UserCreate, UserRead
from ..services.audit import audit_log

router = APIRouter()


@router.post("/register", response_model=UserRead)
def register_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSADMIN")),
):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    role = db.query(Role).filter(Role.id == payload.role_id).first()
    if not role:
        raise HTTPException(status_code=400, detail="Role not found")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role_id=payload.role_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="user.register",
        target_entity_type="User",
        target_entity_id=str(user.id),
        after={"email": user.email, "role_id": user.role_id},
    )
    return user


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .options(joinedload(User.role))
        .filter(User.email == form_data.username)
        .first()
    )
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "role": user.role.name if user.role else None})
    return Token(access_token=token)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/roles", response_model=List[RoleRead])
def list_roles(db: Session = Depends(get_db)) -> List[Role]:
    return db.query(Role).order_by(Role.name.asc()).all()
