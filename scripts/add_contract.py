#!/usr/bin/env python3
"""Quick helper to insert a vendor contract for local testing."""

from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import SessionLocal  # noqa: E402
from backend.models.models import Contract  # noqa: E402


def parse_decimal(value: Optional[str]) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(value)


def parse_date(value: Optional[str]) -> Optional[datetime.date]:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a contract record for quick testing.")
    parser.add_argument("--vendor", required=True, help="Vendor name, e.g. ACME Landscaping")
    parser.add_argument("--service", default=None, help="Service type/category")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--auto-renew", action="store_true", help="Set auto-renew true")
    parser.add_argument("--notice-deadline", default=None, help="Termination notice deadline (YYYY-MM-DD)")
    parser.add_argument("--value", default=None, help="Contract value (numeric)")
    parser.add_argument("--notes", default=None, help="Optional notes")
    args = parser.parse_args()

    with SessionLocal() as session:
        contract = Contract(
            vendor_name=args.vendor,
            service_type=args.service,
            start_date=parse_date(args.start),
            end_date=parse_date(args.end),
            auto_renew=args.auto_renew,
            termination_notice_deadline=parse_date(args.notice_deadline),
            value=parse_decimal(args.value),
            notes=args.notes,
        )
        session.add(contract)
        session.commit()
        session.refresh(contract)

    print(f"Created contract #{contract.id} for {contract.vendor_name}")


if __name__ == "__main__":
    main()
