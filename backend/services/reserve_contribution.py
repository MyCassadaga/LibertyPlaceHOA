from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


DecimalT = Decimal


def _as_decimal(value: Any) -> DecimalT:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True)
class ReserveContributionResult:
    budget_year: int
    target_year: int
    estimated_cost: DecimalT
    inflation_rate: DecimalT
    current_funding: DecimalT
    years_remaining: int
    future_cost: DecimalT
    remaining_needed: DecimalT
    annual_contribution: DecimalT
    future_cost_rounded: DecimalT
    remaining_needed_rounded: DecimalT
    annual_contribution_rounded: DecimalT
    is_valid_target_year: bool


def calculate_reserve_contribution(
    *,
    budget_year: int,
    target_year: int,
    estimated_cost: Any,
    inflation_rate: Any,
    current_funding: Any,
) -> ReserveContributionResult:
    estimated_cost_decimal = _as_decimal(estimated_cost)
    inflation_rate_decimal = _as_decimal(inflation_rate or 0)
    current_funding_decimal = _as_decimal(current_funding or 0)
    years_remaining_raw = target_year - budget_year
    is_valid_target_year = years_remaining_raw > 0
    years_remaining = max(years_remaining_raw, 0)
    future_cost = estimated_cost_decimal * (Decimal("1") + inflation_rate_decimal) ** max(years_remaining, 0)
    remaining_needed = max(future_cost - current_funding_decimal, Decimal("0"))
    if is_valid_target_year and years_remaining > 0:
        annual_contribution = remaining_needed / Decimal(years_remaining)
    else:
        annual_contribution = Decimal("0")
    future_cost_rounded = future_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    remaining_needed_rounded = remaining_needed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    annual_contribution_rounded = annual_contribution.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return ReserveContributionResult(
        budget_year=budget_year,
        target_year=target_year,
        estimated_cost=estimated_cost_decimal,
        inflation_rate=inflation_rate_decimal,
        current_funding=current_funding_decimal,
        years_remaining=years_remaining,
        future_cost=future_cost,
        remaining_needed=remaining_needed,
        annual_contribution=annual_contribution,
        future_cost_rounded=future_cost_rounded,
        remaining_needed_rounded=remaining_needed_rounded,
        annual_contribution_rounded=annual_contribution_rounded,
        is_valid_target_year=is_valid_target_year,
    )
