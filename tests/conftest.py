import sys
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import Base  # noqa: E402
import backend.config as app_config  # noqa: E402
import backend.main as app_main  # noqa: E402
from backend.auth.jwt import get_password_hash  # noqa: E402
# Import the full models module so all tables (including audit_logs) register with Base metadata.
from backend.models import models as _all_models  # noqa: E402,F401
from backend.models.models import Owner, Role, User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _configure_global_test_db(tmp_path_factory):
    """Configure the app-wide SessionLocal/engine so TestClient uses a DB with all tables."""
    db_dir = tmp_path_factory.mktemp("globaldb")
    db_path = db_dir / "app.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    app_config.SessionLocal = SessionLocal
    app_config.engine = engine
    app_main.SessionLocal = SessionLocal
    app_main.engine = engine
    yield
    engine.dispose()


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:
    """Provide a fresh SQLite database for each test."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def create_role(db_session: Session) -> Callable[[str], Role]:
    def _create(name: str) -> Role:
        existing = db_session.query(Role).filter(Role.name == name).first()
        if existing:
            return existing
        role = Role(name=name)
        db_session.add(role)
        db_session.commit()
        return role

    return _create


@pytest.fixture
def create_user(db_session: Session, create_role: Callable[[str], Role]) -> Callable[[str, Optional[str]], User]:
    def _create(email: str = "user@example.com", role_name: str = "SYSADMIN") -> User:
        role = create_role(role_name)
        user = User(email=email, hashed_password=get_password_hash("changeme"), role_id=role.id)
        user.primary_role = role
        user.roles.append(role)
        db_session.add(user)
        db_session.commit()
        return user

    return _create


@pytest.fixture
def create_owner(db_session: Session) -> Callable[[str, str], Owner]:
    counter = {"value": 0}

    def _create(name: str = "Owner", email: str = "owner@example.com") -> Owner:
        counter["value"] += 1
        owner = Owner(
            primary_name=f"{name} {counter['value']}",
            lot=f"LOT-{counter['value']:04d}",
            property_address=f"{counter['value']} Main Street",
            primary_email=email,
        )
        db_session.add(owner)
        db_session.commit()
        return owner

    return _create
