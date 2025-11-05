from typing import Iterable, List, Optional, Sequence

import pyotp
from fastapi import APIRouter, Depends, Form, HTTPException
from jose import JWTError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from ..api.dependencies import get_db
from ..auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_password_hash,
    require_roles,
    verify_password,
)
from ..config import settings
from ..constants import ROLE_PRIORITY
from ..models.models import Owner, OwnerUserLink, Role, User, user_roles
from ..schemas.schemas import (
    PasswordChange,
    RoleRead,
    TokenRefreshRequest,
    Token,
    TwoFactorSetupResponse,
    TwoFactorVerifyRequest,
    UserCreate,
    UserRead,
    UserRoleUpdate,
    UserSelfUpdate,
)
from ..services.audit import audit_log

router = APIRouter()


class OAuth2PasswordRequestFormWithOTP:
    def __init__(
        self,
        grant_type: str = Form(default="password"),
        username: str = Form(...),
        password: str = Form(...),
        scope: str = Form(""),
        client_id: Optional[str] = Form(None),
        client_secret: Optional[str] = Form(None),
        otp: Optional[str] = Form(None),
    ) -> None:
        self.grant_type = grant_type
        self.username = username
        self.password = password
        self.scopes = scope.split()
        self.client_id = client_id
        self.client_secret = client_secret
        self.otp = otp


def _sort_roles_by_priority(roles: Sequence[Role]) -> List[Role]:
    return sorted(roles, key=lambda role: ROLE_PRIORITY.get(role.name, 0), reverse=True)


def _apply_roles_to_user(user: User, roles: Iterable[Role]) -> None:
    unique_roles: dict[int, Role] = {}
    for role in roles:
        unique_roles[role.id] = role

    ordered_roles = _sort_roles_by_priority(list(unique_roles.values()))
    user.roles = ordered_roles
    if ordered_roles:
        user.role_id = ordered_roles[0].id


def _ensure_homeowner_link(db: Session, user: User, preferred_name: str | None = None) -> None:
    if not user.has_role("HOMEOWNER"):
        return

    existing_link = (
        db.query(OwnerUserLink)
        .filter(OwnerUserLink.user_id == user.id)
        .first()
    )
    if existing_link:
        return

    email = (user.email or "").lower()
    owner = (
        db.query(Owner)
        .filter(
            Owner.is_archived.is_(False),
            or_(
                func.lower(Owner.primary_email) == email,
                func.lower(Owner.secondary_email) == email,
            ),
        )
        .first()
    )

    created_owner = False
    if not owner:
        display_name = preferred_name or user.full_name or user.email or "Homeowner"
        owner = Owner(
            primary_name=display_name,
            lot=f"USER-{user.id:04d}",
            property_address=f"Pending address for {display_name}",
            primary_email=user.email,
        )
        db.add(owner)
        db.flush()
        created_owner = True

    link = OwnerUserLink(owner_id=owner.id, user_id=user.id, link_type="PRIMARY")
    db.add(link)
    db.flush()


def _verify_otp(user: User, otp: Optional[str]) -> None:
    if not user.two_factor_secret:
        raise HTTPException(status_code=400, detail="Two-factor secret not configured.")
    if not otp:
        raise HTTPException(status_code=401, detail="Two-factor code required.")
    totp = pyotp.TOTP(user.two_factor_secret)
    if not totp.verify(otp, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid two-factor code.")


def _build_token_response(user: User) -> Token:
    primary_role = user.highest_priority_role or user.role
    primary_role_name = primary_role.name if primary_role else None
    role_names = [role.name for role in user.roles] or ([primary_role_name] if primary_role_name else [])

    access_payload = {
        "sub": str(user.id),
        "roles": role_names,
        "primary_role": primary_role_name,
        "type": "access",
    }
    access_token = create_access_token(access_payload)
    refresh_token = create_refresh_token(str(user.id))

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        roles=role_names,
        primary_role=primary_role_name,
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_expires_in=settings.refresh_token_expire_minutes * 60,
    )

@router.post("/register", response_model=UserRead)
def register_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSADMIN")),
):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    requested_role_ids = set(payload.role_ids)
    roles = (
        db.query(Role)
        .filter(Role.id.in_(requested_role_ids))
        .all()
    )
    if len(roles) != len(requested_role_ids):
        raise HTTPException(status_code=400, detail="One or more roles not found")
    ordered_roles = _sort_roles_by_priority(roles)
    primary_role = ordered_roles[0]

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role_id=primary_role.id,
    )
    db.add(user)
    db.flush()

    _apply_roles_to_user(user, ordered_roles)
    db.flush()

    _ensure_homeowner_link(db, user, payload.full_name)

    db.commit()

    user = (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .get(user.id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found after creation.")

    role_snapshot = [role.name for role in user.roles] or ([user.role.name] if user.role else [])

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="user.register",
        target_entity_type="User",
        target_entity_id=str(user.id),
        after={"email": user.email, "roles": role_snapshot},
    )
    return user


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestFormWithOTP = Depends(),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .filter(User.email == form_data.username)
        .first()
    )
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is archived or inactive.")

    if user.two_factor_enabled:
        _verify_otp(user, form_data.otp)

    return _build_token_response(user)


@router.post("/refresh", response_model=Token)
def refresh_token(
    payload: TokenRefreshRequest,
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(status_code=401, detail="Invalid refresh token")
    try:
        decoded = decode_token(payload.refresh_token)
    except JWTError as exc:  # pragma: no cover - defensive
        raise credentials_exception from exc

    if decoded.get("type") != "refresh":
        raise credentials_exception

    user_id = decoded.get("sub")
    if not user_id:
        raise credentials_exception

    user = (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .get(int(user_id))
    )
    if not user or not user.is_active:
        raise credentials_exception

    return _build_token_response(user)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
def update_current_user_profile(
    payload: UserSelfUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    updates = payload.dict(exclude_unset=True)
    db_user = (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .filter(User.id == current_user.id)
        .first()
    )
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    if not updates:
        return db_user

    before = {"email": db_user.email, "full_name": db_user.full_name}
    current_password = updates.pop("current_password", None)
    email_changed = False

    if "email" in updates:
        new_email = updates["email"]
        if new_email and (db_user.email or "").lower() != new_email.lower():
            if not current_password or not verify_password(current_password, db_user.hashed_password):
                raise HTTPException(status_code=400, detail="Current password required to change email.")
            existing = (
                db.query(User)
                .filter(User.email == new_email, User.id != current_user.id)
                .first()
            )
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use.")
            db_user.email = new_email
            email_changed = True

    if "full_name" in updates:
        db_user.full_name = updates["full_name"]

    db.commit()

    refreshed = (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .filter(User.id == current_user.id)
        .first()
    )
    if not refreshed:
        raise HTTPException(status_code=404, detail="User not found after update.")

    after = {"email": refreshed.email, "full_name": refreshed.full_name}
    if before != after or email_changed:
        audit_log(
            db_session=db,
            actor_user_id=current_user.id,
            action="user.profile_update",
            target_entity_type="User",
            target_entity_id=str(current_user.id),
            before=before,
            after=after,
        )

    return refreshed


@router.post("/me/change-password")
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_user = db.get(User, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    if not verify_password(payload.current_password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    db_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()

    audit_log(
        db_session=db,
        actor_user_id=current_user.id,
        action="user.password_change",
        target_entity_type="User",
        target_entity_id=str(current_user.id),
        after={"password_changed": True},
    )

    return {"message": "Password updated."}


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
def setup_two_factor(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwoFactorSetupResponse:
    secret = pyotp.random_base32()
    db_user = (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .filter(User.id == current_user.id)
        .first()
    )
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.two_factor_secret = secret
    db_user.two_factor_enabled = False
    db.add(db_user)
    db.commit()

    totp = pyotp.TOTP(secret)
    otpauth_url = totp.provisioning_uri(name=db_user.email or "user", issuer_name="Liberty Place HOA")
    
    return TwoFactorSetupResponse(secret=secret, otpauth_url=otpauth_url)


@router.post("/2fa/enable")
def enable_two_factor(
    payload: TwoFactorVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_user = (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .filter(User.id == current_user.id)
        .first()
    )
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")
    if not db_user.two_factor_secret:
        raise HTTPException(status_code=400, detail="Generate a 2FA secret before enabling.")
    _verify_otp(db_user, payload.otp)
    db_user.two_factor_enabled = True
    db.add(db_user)
    db.commit()
    return {"message": "Two-factor authentication enabled."}


@router.post("/2fa/disable")
def disable_two_factor(
    payload: TwoFactorVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_user = (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .filter(User.id == current_user.id)
        .first()
    )
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")
    if not db_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="Two-factor authentication is not enabled.")
    _verify_otp(db_user, payload.otp)
    db_user.two_factor_enabled = False
    db_user.two_factor_secret = None
    db.add(db_user)
    db.commit()
    return {"message": "Two-factor authentication disabled."}


@router.get("/roles", response_model=List[RoleRead])
def list_roles(db: Session = Depends(get_db)) -> List[Role]:
    return db.query(Role).order_by(Role.name.asc()).all()


@router.patch("/users/{user_id}/roles", response_model=UserRead)
def update_user_roles(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSADMIN")),
) -> User:
    requested_role_ids = set(payload.role_ids)
    if not requested_role_ids:
        raise HTTPException(status_code=400, detail="At least one role is required.")

    user = (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .get(user_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    roles = (
        db.query(Role)
        .filter(Role.id.in_(requested_role_ids))
        .all()
    )
    if len(roles) != len(requested_role_ids):
        raise HTTPException(status_code=400, detail="One or more roles not found")

    before_roles = sorted({role.name for role in user.roles} or ([user.role.name] if user.role else []))
    requested_role_names = {role.name for role in roles}

    if "SYSADMIN" not in requested_role_names:
        remaining_sysadmins = (
            db.query(User)
            .join(user_roles, user_roles.c.user_id == User.id)
            .join(Role, Role.id == user_roles.c.role_id)
            .filter(Role.name == "SYSADMIN", User.id != user.id, User.is_active.is_(True))
            .count()
        )
        if remaining_sysadmins == 0:
            raise HTTPException(status_code=400, detail="The system must retain at least one active SYSADMIN.")

    _apply_roles_to_user(user, roles)
    db.flush()

    _ensure_homeowner_link(db, user, user.full_name)

    db.commit()

    refreshed = (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .get(user.id)
    )
    if not refreshed:
        raise HTTPException(status_code=404, detail="User not found after update.")

    after_roles = sorted({role.name for role in refreshed.roles} or ([refreshed.role.name] if refreshed.role else []))

    if before_roles != after_roles:
        audit_log(
            db_session=db,
            actor_user_id=actor.id,
            action="user.roles_update",
            target_entity_type="User",
            target_entity_id=str(user.id),
            before={"roles": before_roles},
            after={"roles": after_roles},
        )

    return refreshed


@router.get("/users", response_model=List[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SECRETARY", "SYSADMIN")),
) -> List[User]:
    return (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .order_by(User.created_at.asc())
        .all()
    )
