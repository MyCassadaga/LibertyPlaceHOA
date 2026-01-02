#!/usr/bin/env python3
"""Run scheduled autopay charges for invoices posted 30 days ago."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import SessionLocal  # noqa: E402
from backend.services.autopay import run_autopay_charges  # noqa: E402


def main() -> None:
    with SessionLocal() as session:
        paid_invoice_ids = run_autopay_charges(session)
    if paid_invoice_ids:
        print(f"Autopay processed invoices: {', '.join(str(invoice_id) for invoice_id in paid_invoice_ids)}")
    else:
        print("No autopay charges due.")


if __name__ == "__main__":
    main()
