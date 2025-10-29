from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import require_roles
from ..models.models import User
from ..services.reports import generate_ar_aging_report, generate_cash_flow_report

router = APIRouter()


def _csv_response(filename: str, content: str) -> Response:
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    }
    return Response(content=content, media_type="text/csv", headers=headers)


@router.get("/reports/ar-aging.csv")
def export_ar_aging(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN", "AUDITOR")),
) -> Response:
    report = generate_ar_aging_report(db)
    return _csv_response(report.filename, report.content)


@router.get("/reports/cash-flow.csv")
def export_cash_flow(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN", "AUDITOR")),
) -> Response:
    report = generate_cash_flow_report(db)
    return _csv_response(report.filename, report.content)
