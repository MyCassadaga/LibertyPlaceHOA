from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session, joinedload

from ..config import SessionLocal, settings
from ..constants import ROLE_PRIORITY
from ..models.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
optional_bearer = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def _create_token(data: dict, expires_minutes: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload.setdefault("type", "access")
    return _create_token(payload, settings.access_token_expire_minutes)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "type": "refresh"}
    return _create_token(payload, settings.refresh_token_expire_minutes)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: Optional[str] = payload.get("sub")
        token_type = payload.get("type")
        if user_id is None or token_type not in (None, "access"):
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .filter(User.id == int(user_id))
        .first()
    )
    if user is None:
        raise credentials_exception
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(optional_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    token = credentials.credentials
    try:
        payload = decode_token(token)
        user_id: Optional[str] = payload.get("sub")
        token_type = payload.get("type")
        if user_id is None or token_type not in (None, "access"):
            return None
    except JWTError:
        return None

    user = (
        db.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .filter(User.id == int(user_id))
        .first()
    )
    return user


def require_roles(*allowed_roles: str):
    allowed = set(allowed_roles)

    def role_checker(user: User = Depends(get_current_user)) -> User:
        if not allowed:
            return user
        if user.has_any_role(*allowed):
            return user
        raise HTTPException(status_code=403, detail="Operation not permitted for your role")

    return role_checker


def require_minimum_role(role_name: str):
    minimum = ROLE_PRIORITY.get(role_name, 0)

    def min_checker(user: User = Depends(get_current_user)) -> User:
        highest = user.highest_priority_role
        if highest and ROLE_PRIORITY.get(highest.name, 0) >= minimum:
            return user
        raise HTTPException(status_code=403, detail="Insufficient privileges for this action")

    return min_checker
