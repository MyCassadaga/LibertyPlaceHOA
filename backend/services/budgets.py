from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Tuple

from sqlalchemy.orm import Session

from ..models.models import Budget, Role, User, user_roles, ReservePlanItem


DecimalT = Decimal


def _as_decimal(value) -> DecimalT:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def compute_totals(budget: Budget) -> Tuple[DecimalT, DecimalT, DecimalT]:
    operations_total = Decimal("0")
    reserves_total = Decimal("0")
    for item in budget.line_items:
        amount = _as_decimal(item.amount)
        if item.is_reserve:
            reserves_total += amount
        else:
            operations_total += amount
    reserves_total += _calculate_reserve_contributions(budget)
    total = operations_total + reserves_total
    return (
        operations_total.quantize(Decimal("0.01")),
        reserves_total.quantize(Decimal("0.01")),
        total.quantize(Decimal("0.01")),
    )


def _calculate_reserve_contributions(budget: Budget) -> DecimalT:
    total = Decimal("0")
    for item in budget.reserve_items:
        annual = _reserve_item_annual_contribution(budget.year, item)
        total += annual
    return total


def _reserve_item_annual_contribution(budget_year: int, item: ReservePlanItem) -> DecimalT:
    years_remaining = max(item.target_year - budget_year, 1)
    inflation_rate = Decimal(str(item.inflation_rate or 0))
    projected_cost = _as_decimal(item.estimated_cost) * (Decimal("1") + inflation_rate) ** years_remaining
    remaining = projected_cost - _as_decimal(item.current_funding)
    if remaining <= 0:
        return Decimal("0")
    return (remaining / Decimal(years_remaining)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_assessment(total_annual: DecimalT, home_count: int) -> DecimalT:
    if home_count <= 0:
        return Decimal("0.00")
    quarterly = (total_annual / Decimal(home_count) / Decimal("4")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return quarterly


def get_active_board_member_ids(session: Session) -> List[int]:
    rows = (
        session.query(User.id)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .filter(Role.name == "BOARD", User.is_active.is_(True))
        .distinct()
        .all()
    )
    return [row[0] for row in rows]


def calculate_required_board_approvals(session: Session) -> int:
    board_ids = get_active_board_member_ids(session)
    if not board_ids:
        return 0
    required = math.ceil(len(board_ids) * (2 / 3))
    return max(1, required)


def ensure_next_year_draft(session: Session) -> None:
    today = datetime.now(timezone.utc).date()
    if today.month < 12:
        return
    target_year = today.year + 1
    exists = session.query(Budget).filter(Budget.year == target_year).first()
    if exists:
        return
    draft = Budget(year=target_year, status="DRAFT", home_count=0)
    session.add(draft)
    session.commit()
