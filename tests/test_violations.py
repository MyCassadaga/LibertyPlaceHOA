from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from backend.models.models import AuditLog, Violation, ViolationNotice
from backend.services import violations
from backend.services.violations import transition_violation


def test_violation_transition_updates_status_and_logs(db_session, create_user, create_owner):
    actor = create_user(role_name="SYSADMIN")
    owner = create_owner()
    violation = Violation(
        owner_id=owner.id,
        reported_by_user_id=actor.id,
        status="NEW",
        category="Trash",
        description="Trash cans left out",
    )
    db_session.add(violation)
    db_session.commit()

    transition_violation(db_session, violation, actor, "UNDER_REVIEW", note="Investigating")

    refreshed = db_session.query(Violation).filter(Violation.id == violation.id).one()
    assert refreshed.status == "UNDER_REVIEW"

    audit_entry = db_session.query(AuditLog).filter(AuditLog.action == "violations.transition").one()
    assert '"status": "UNDER_REVIEW"' in (audit_entry.after or "")
    assert '"status": "NEW"' in (audit_entry.before or "")


def test_violation_transition_generates_notice_and_email(
    tmp_path,
    db_session,
    create_user,
    create_owner,
    monkeypatch,
):
    actor = create_user(role_name="SYSADMIN")
    owner = create_owner()
    violation = Violation(
        owner_id=owner.id,
        reported_by_user_id=actor.id,
        status="UNDER_REVIEW",
        category="Parking",
        description="Unauthorized vehicle",
        due_date=date.today(),
    )
    db_session.add(violation)
    db_session.commit()

    notices_dir = tmp_path / "notices"
    notices_dir.mkdir()
    monkeypatch.setattr(violations, "NOTICE_DIRECTORY", notices_dir)

    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_text("pdf-body")

    monkeypatch.setattr(
        violations,
        "generate_violation_notice_pdf",
        lambda *args, **kwargs: str(source_pdf),
    )

    sent_payloads = []

    def _fake_send(subject, body, recipients):
        sent_payloads.append((subject, body, tuple(recipients)))
        return recipients

    monkeypatch.setattr(violations.email, "send_announcement", _fake_send)

    sent_notifications = []

    def _fake_notification(session, **kwargs):
        sent_notifications.append(kwargs)
        return []

    monkeypatch.setattr(violations, "create_notification", _fake_notification)

    transition_violation(
        db_session,
        violation,
        actor,
        "WARNING_SENT",
        fine_amount=Decimal("0"),
    )

    notice = db_session.query(ViolationNotice).filter_by(violation_id=violation.id).one()
    assert notice.template_key == "WARNING_SENT"
    stored_name = Path(notice.pdf_path).name
    assert (violations.NOTICE_DIRECTORY / stored_name).exists()
    assert sent_payloads, "Expected email notification to be triggered"
    assert owner.primary_email in sent_payloads[0][2]
    assert sent_notifications, "Expected at least one notification payload"


def test_violation_transition_rejects_invalid_target(db_session, create_user, create_owner):
    actor = create_user(role_name="SYSADMIN")
    owner = create_owner()
    violation = Violation(
        owner_id=owner.id,
        reported_by_user_id=actor.id,
        status="NEW",
        category="Noise",
    )
    db_session.add(violation)
    db_session.commit()

    with pytest.raises(ValueError):
        transition_violation(db_session, violation, actor, "RESOLVED")
