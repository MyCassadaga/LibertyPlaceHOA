from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Tuple

from sqlalchemy.orm import Session

from ..models.models import Budget, BudgetLineItem, Role, User, user_roles, ReservePlanItem
from .reserve_contribution import calculate_reserve_contribution


DecimalT = Decimal


RESERVE_LINE_ITEM_SOURCE = "RESERVE_PLAN"


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
    total = operations_total + reserves_total
    return (
        operations_total.quantize(Decimal("0.01")),
        reserves_total.quantize(Decimal("0.01")),
        total.quantize(Decimal("0.01")),
    )


def upsert_reserve_line_item(budget: Budget, item: ReservePlanItem) -> BudgetLineItem:
    calculation = calculate_reserve_contribution(
        budget_year=budget.year,
        target_year=item.target_year,
        estimated_cost=item.estimated_cost,
        inflation_rate=item.inflation_rate,
        current_funding=item.current_funding,
    )
    line_item = next(
        (
            entry
            for entry in budget.line_items
            if entry.source_type == RESERVE_LINE_ITEM_SOURCE and entry.source_id == item.id
        ),
        None,
    )
    label = f"Reserve: {item.name}"
    if line_item is None:
        line_item = BudgetLineItem(
            budget_id=budget.id,
            label=label,
            category="Reserve Contribution",
            amount=calculation.annual_contribution_rounded,
            is_reserve=True,
            sort_order=0,
            source_type=RESERVE_LINE_ITEM_SOURCE,
            source_id=item.id,
        )
    else:
        line_item.label = label
        line_item.category = "Reserve Contribution"
        line_item.amount = calculation.annual_contribution_rounded
        line_item.is_reserve = True
        line_item.sort_order = line_item.sort_order or 0
        line_item.source_type = RESERVE_LINE_ITEM_SOURCE
        line_item.source_id = item.id
    return line_item


def delete_reserve_line_item(budget: Budget, item: ReservePlanItem) -> BudgetLineItem | None:
    return next(
        (
            entry
            for entry in budget.line_items
            if entry.source_type == RESERVE_LINE_ITEM_SOURCE and entry.source_id == item.id
        ),
        None,
    )


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
