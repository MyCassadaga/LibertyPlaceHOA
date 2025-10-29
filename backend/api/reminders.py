from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import require_roles
from ..models.models import Reminder, User
from ..schemas.schemas import ReminderRead

router = APIRouter()


@router.get("/dashboard/reminders", response_model=List[ReminderRead])
def list_dashboard_reminders(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SECRETARY", "SYSADMIN")),
) -> List[Reminder]:
    return (
        db.query(Reminder)
        .filter(Reminder.reminder_type == "renewal_warning", Reminder.resolved_at.is_(None))
        .order_by(Reminder.due_date.asc().nulls_last(), Reminder.title.asc())
        .all()
    )
