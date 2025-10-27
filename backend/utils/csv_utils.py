import csv
from io import StringIO
from typing import Iterable, List, Sequence


def rows_to_csv(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def ledger_to_csv(ledger_entries: List) -> str:
    headers = ["timestamp", "entry_type", "amount", "balance_after", "description"]
    rows = []
    for entry in ledger_entries:
        rows.append(
            [
                entry.timestamp.isoformat(),
                entry.entry_type,
                str(entry.amount),
                str(entry.balance_after or ""),
                entry.description or "",
            ]
        )
    return rows_to_csv(headers, rows)
