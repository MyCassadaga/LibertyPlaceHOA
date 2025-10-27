from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .api import auth, billing, comms, contracts, owners
from .config import Base, SessionLocal, engine, settings
from .constants import DEFAULT_ROLES
from .models.models import Permission, Role

app = FastAPI(title="Liberty Place HOA - Phase 1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ensure_default_roles(session: Session) -> None:
    for name, description in DEFAULT_ROLES:
        role = session.query(Role).filter(Role.name == name).first()
        if not role:
            role = Role(name=name, description=description)
            session.add(role)
    session.commit()

    # Create generic permissions placeholder to demonstrate RBAC expansion
    default_permissions = ["owners:read", "owners:write", "billing:read", "billing:write", "contracts:read", "contracts:write"]
    for perm_name in default_permissions:
        permission = session.query(Permission).filter(Permission.name == perm_name).first()
        if not permission:
            session.add(Permission(name=perm_name))
    session.commit()


@app.on_event("startup")
def startup() -> None:
    # In dev we make sure tables exist. Alembic migrations should be used for real schema evolution.
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        ensure_default_roles(session)


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(owners.router, prefix="/owners", tags=["owners"])
app.include_router(billing.router, prefix="/billing", tags=["billing"])
app.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
app.include_router(comms.router, prefix="/communications", tags=["communications"])
