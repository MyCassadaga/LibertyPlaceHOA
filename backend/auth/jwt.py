from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session, joinedload

from ..config import SessionLocal, settings
from ..constants import ROLE_PRIORITY
from ..models.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


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
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).options(joinedload(User.role)).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


def require_roles(*allowed_roles: str):
    allowed = set(allowed_roles)

    def role_checker(user: User = Depends(get_current_user)) -> User:
        if not allowed:
            return user
        if user.role and user.role.name in allowed:
            return user
        raise HTTPException(status_code=403, detail="Operation not permitted for your role")

    return role_checker


def require_minimum_role(role_name: str):
    minimum = ROLE_PRIORITY.get(role_name, 0)

    def min_checker(user: User = Depends(get_current_user)) -> User:
        user_role = user.role.name if user.role else None
        if user_role and ROLE_PRIORITY.get(user_role, 0) >= minimum:
            return user
        raise HTTPException(status_code=403, detail="Insufficient privileges for this action")

    return min_checker
