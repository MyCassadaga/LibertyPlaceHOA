import asyncio
import logging
from io import BytesIO

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload

from .api import (
    arc,
    auth,
    audit_logs,
    banking,
    billing,
    budgets,
    comms,
    contracts,
    documents,
    elections,
    meetings,
    notifications,
    notices,
    owners,
    paperwork,
    payments,
    reminders,
    reports,
    violations,
    system,
)
from .config import Base, SessionLocal, engine, settings
from decimal import Decimal

from .constants import DEFAULT_LATE_FEE_POLICY, DEFAULT_ROLES
from .models.models import BillingPolicy, LateFeeTier, NoticeType, Owner, OwnerUserLink, Permission, Role, User
from .auth.jwt import get_current_user, decode_token
from .services import budgets as budget_service
from .services.reminders import generate_contract_renewal_reminders
from .services.audit import audit_log
from .services.notifications import notification_center
from .services.backup import perform_sqlite_backup
from .services.storage import StorageBackend, storage_service

logger = logging.getLogger(__name__)


def ensure_homeowner_owner_records(session: Session) -> None:
    homeowners = (
        session.query(User)
        .join(Role)
        .filter(Role.name == "HOMEOWNER")
        .all()
    )
    owners_by_email = {
        (owner.primary_email or "").lower(): owner
        for owner in session.query(Owner).all()
    }

    for user in homeowners:
        email = (user.email or "").lower()
        owner = owners_by_email.get(email)
        if not email:
            continue
        if not owner:
            primary_name = user.full_name or user.email or "Homeowner"
            owner = Owner(
                primary_name=primary_name,
                lot=f"USER-{user.id:04d}",
                property_address=f"Pending address for {primary_name}",
                primary_email=user.email,
            )
            session.add(owner)
            session.commit()
            session.refresh(owner)
            owners_by_email[email] = owner

        link_exists = (
            session.query(OwnerUserLink)
            .filter(OwnerUserLink.owner_id == owner.id, OwnerUserLink.user_id == user.id)
            .first()
        )
        if not link_exists:
            session.add(OwnerUserLink(owner_id=owner.id, user_id=user.id, link_type="PRIMARY"))
            session.commit()

app = FastAPI(title="Liberty Place HOA - Phase 1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

uploads_route = "/" + settings.uploads_public_prefix.strip("/")
if storage_service.backend == StorageBackend.LOCAL:
    uploads_dir = settings.uploads_root_path
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount(uploads_route, StaticFiles(directory=str(uploads_dir)), name="uploads")
else:

    @app.get(f"{uploads_route}/{{path:path}}", include_in_schema=False)
    def proxy_uploads(path: str):
        file_data = storage_service.retrieve_file(path)
        return StreamingResponse(BytesIO(file_data.content), media_type=file_data.content_type)


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


def ensure_user_role_links(session: Session) -> None:
    users = (
        session.query(User)
        .options(joinedload(User.primary_role), joinedload(User.roles))
        .all()
    )
    updated = False
    for user in users:
        if not user.roles:
            primary = user.role or user.primary_role
            if primary:
                user.roles.append(primary)
                updated = True
    if updated:
        session.commit()


def ensure_billing_policy(session: Session) -> None:
    policy_defaults = DEFAULT_LATE_FEE_POLICY
    policy = (
        session.query(BillingPolicy)
        .filter(BillingPolicy.name == policy_defaults["name"])
        .first()
    )
    if not policy:
        policy = BillingPolicy(
            name=policy_defaults["name"],
            grace_period_days=policy_defaults["grace_period_days"],
            dunning_schedule_days=policy_defaults["dunning_schedule_days"],
        )
        session.add(policy)
        session.flush()
    else:
        policy.grace_period_days = policy_defaults["grace_period_days"]
        policy.dunning_schedule_days = policy_defaults["dunning_schedule_days"]

    existing_tiers_by_sequence = {tier.sequence_order: tier for tier in policy.tiers}
    desired_sequences = set()
    for tier_payload in policy_defaults["tiers"]:
        desired_sequences.add(tier_payload["sequence_order"])
        tier = existing_tiers_by_sequence.get(tier_payload["sequence_order"])
        if not tier:
            tier = LateFeeTier(policy_id=policy.id, sequence_order=tier_payload["sequence_order"])
        tier.trigger_days_after_grace = tier_payload["trigger_days_after_grace"]
        tier.fee_type = tier_payload["fee_type"]
        tier.fee_amount = Decimal(str(tier_payload["fee_amount"]))
        tier.fee_percent = tier_payload["fee_percent"]
        tier.description = tier_payload.get("description")
        session.add(tier)
        session.flush()

    for tier in list(policy.tiers):
        if tier.sequence_order not in desired_sequences:
            session.delete(tier)

    session.commit()


NOTICE_TYPE_SEED = [
    {
        "code": "ANNUAL_MEETING",
        "name": "Annual Meeting Notice",
        "description": "Required notice for annual meetings.",
        "allow_electronic": True,
        "requires_paper": False,
        "default_delivery": "AUTO",
    },
    {
        "code": "NEWSLETTER",
        "name": "Newsletter",
        "description": "General community newsletter.",
        "allow_electronic": True,
        "requires_paper": False,
        "default_delivery": "AUTO",
    },
    {
        "code": "DELINQUENCY_FIRST",
        "name": "Delinquency (First Notice)",
        "description": "First delinquency reminder.",
        "allow_electronic": True,
        "requires_paper": True,
        "default_delivery": "AUTO",
    },
    {
        "code": "LIEN_NOTICE",
        "name": "Lien Notice",
        "description": "Lien filing notice.",
        "allow_electronic": True,
        "requires_paper": True,
        "default_delivery": "PAPER_ONLY",
    },
    {
        "code": "FINE_IMPOSITION",
        "name": "Fine Imposition Notice",
        "description": "Notice of fine imposed.",
        "allow_electronic": True,
        "requires_paper": True,
        "default_delivery": "AUTO",
    },
    {
        "code": "VIOLATION_NOTICE",
        "name": "Violation Notice",
        "description": "Covenant violation notice.",
        "allow_electronic": True,
        "requires_paper": True,
        "default_delivery": "AUTO",
    },
]


def ensure_notice_types(session: Session) -> None:
    existing = {nt.code: nt for nt in session.query(NoticeType).all()}
    updated = False
    for entry in NOTICE_TYPE_SEED:
        notice = existing.get(entry["code"])
        if not notice:
            notice = NoticeType(**entry)
            session.add(notice)
            updated = True
        else:
            changed = False
            for field in ("name", "description", "allow_electronic", "requires_paper", "default_delivery"):
                if getattr(notice, field) != entry[field]:
                    setattr(notice, field, entry[field])
                    changed = True
            if changed:
                updated = True
    if updated:
        session.commit()


@app.on_event("startup")
def startup() -> None:
    # In dev we make sure tables exist. Alembic migrations should be used for real schema evolution.
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        ensure_default_roles(session)
        ensure_user_role_links(session)
        ensure_billing_policy(session)
        ensure_notice_types(session)
        created_reminders = generate_contract_renewal_reminders(session)
        if created_reminders:
            session.commit()
        ensure_homeowner_owner_records(session)
        budget_service.ensure_next_year_draft(session)


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(owners.router, prefix="/owners", tags=["owners"])
app.include_router(billing.router, prefix="/billing", tags=["billing"])
app.include_router(budgets.router)
app.include_router(notices.router)
app.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
app.include_router(comms.router, prefix="/communications", tags=["communications"])
app.include_router(reminders.router, tags=["dashboard"])
app.include_router(reports.router, tags=["reports"])
app.include_router(violations.router, prefix="/violations", tags=["violations"])
app.include_router(arc.router, tags=["arc"])
app.include_router(banking.router, tags=["banking"])
app.include_router(elections.router, prefix="/elections", tags=["elections"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(paperwork.router)
app.include_router(documents.router)
app.include_router(meetings.router)
app.include_router(audit_logs.router)
app.include_router(system.router, prefix="/system", tags=["system"])
app.include_router(payments.router, prefix="/payments", tags=["payments"])


@app.middleware("http")
async def audit_trail(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/notifications/ws"):
        return response
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return response
    actor_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
            actor_id = int(payload.get("sub"))
        except Exception:  # pragma: no cover - defensive
            actor_id = None
    with SessionLocal() as session:
        audit_log(
            db_session=session,
            actor_user_id=actor_id,
            action=f"{request.method} {request.url.path}",
            target_entity_type="HTTP",
            target_entity_id=request.url.path,
            after={"status": response.status_code},
        )
    return response


@app.on_event("shutdown")
def shutdown() -> None:
    """Create a SQLite backup when the application stops."""
    try:
        backup_path = perform_sqlite_backup()
        if backup_path:
            logger.info("SQLite backup created at %s", backup_path)
    except Exception:
        logger.exception("Failed to create SQLite backup during shutdown.")


@app.on_event("startup")
async def configure_notification_center() -> None:
    notification_center.configure_loop(asyncio.get_running_loop())


@app.on_event("shutdown")
async def shutdown_notification_center() -> None:
    await notification_center.shutdown()
