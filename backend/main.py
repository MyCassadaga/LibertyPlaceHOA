from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .api import auth, billing, comms, contracts, owners, reminders, reports
from .config import Base, SessionLocal, engine, settings
from decimal import Decimal

from .constants import DEFAULT_LATE_FEE_POLICY, DEFAULT_ROLES
from .models.models import BillingPolicy, LateFeeTier, Permission, Role
from .services.reminders import generate_contract_renewal_reminders

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


@app.on_event("startup")
def startup() -> None:
    # In dev we make sure tables exist. Alembic migrations should be used for real schema evolution.
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        ensure_default_roles(session)
        ensure_billing_policy(session)
        created_reminders = generate_contract_renewal_reminders(session)
        if created_reminders:
            session.commit()


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(owners.router, prefix="/owners", tags=["owners"])
app.include_router(billing.router, prefix="/billing", tags=["billing"])
app.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
app.include_router(comms.router, prefix="/communications", tags=["communications"])
app.include_router(reminders.router, tags=["dashboard"])
app.include_router(reports.router, tags=["reports"])
