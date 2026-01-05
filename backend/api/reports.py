from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import require_roles
from ..models.models import User
from ..services.audit import audit_log
from ..schemas.schemas import (
    ARAgingReportRow,
    ArcSlaReportRow,
    CashFlowReportRow,
    ViolationsSummaryReportRow,
)
from ..services.reports import (
    generate_ar_aging_report,
    generate_cash_flow_report,
    generate_violations_summary_report,
    generate_arc_sla_report,
    get_ar_aging_data,
    get_cash_flow_data,
    get_violations_summary_data,
    get_arc_sla_data,
)

router = APIRouter()


def _csv_response(filename: str, content: str) -> Response:
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    }
    return Response(content=content, media_type="text/csv", headers=headers)


def _audit_report_access(session: Session, actor: User, action: str) -> None:
    audit_log(
        db_session=session,
        actor_user_id=actor.id,
        action=action,
        target_entity_type="Report",
        target_entity_id=action,
    )


@router.get("/reports/ar-aging")
def export_ar_aging(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN")),
) -> Response:
    report = generate_ar_aging_report(db)
    _audit_report_access(db, actor, "reports.ar_aging")
    return _csv_response(report.filename, report.content)


@router.get("/reports/ar-aging/data", response_model=list[ARAgingReportRow])
def list_ar_aging_data(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN")),
) -> list[ARAgingReportRow]:
    rows = get_ar_aging_data(db)
    _audit_report_access(db, actor, "reports.ar_aging.data")
    return rows


@router.get("/reports/cash-flow")
def export_cash_flow(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN")),
) -> Response:
    report = generate_cash_flow_report(db)
    _audit_report_access(db, actor, "reports.cash_flow")
    return _csv_response(report.filename, report.content)


@router.get("/reports/cash-flow/data", response_model=list[CashFlowReportRow])
def list_cash_flow_data(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN")),
) -> list[CashFlowReportRow]:
    rows = get_cash_flow_data(db)
    _audit_report_access(db, actor, "reports.cash_flow.data")
    return rows


@router.get("/reports/violations-summary")
def export_violations_summary(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN")),
) -> Response:
    report = generate_violations_summary_report(db)
    _audit_report_access(db, actor, "reports.violations_summary")
    return _csv_response(report.filename, report.content)


@router.get("/reports/violations-summary/data", response_model=list[ViolationsSummaryReportRow])
def list_violations_summary_data(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN")),
) -> list[ViolationsSummaryReportRow]:
    rows = get_violations_summary_data(db)
    _audit_report_access(db, actor, "reports.violations_summary.data")
    return rows


@router.get("/reports/arc-sla")
def export_arc_sla(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN")),
) -> Response:
    report = generate_arc_sla_report(db)
    _audit_report_access(db, actor, "reports.arc_sla")
    return _csv_response(report.filename, report.content)


@router.get("/reports/arc-sla/data", response_model=list[ArcSlaReportRow])
def list_arc_sla_data(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN")),
) -> list[ArcSlaReportRow]:
    rows = get_arc_sla_data(db)
    _audit_report_access(db, actor, "reports.arc_sla.data")
    return rows


# Legacy compatibility endpoints
@router.get("/reports/ar-aging.csv")
def export_ar_aging_legacy(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN")),
) -> Response:
    report = generate_ar_aging_report(db)
    _audit_report_access(db, actor, "reports.ar_aging")
    return _csv_response(report.filename, report.content)


@router.get("/reports/cash-flow.csv")
def export_cash_flow_legacy(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN")),
) -> Response:
    report = generate_cash_flow_report(db)
    _audit_report_access(db, actor, "reports.cash_flow")
    return _csv_response(report.filename, report.content)
