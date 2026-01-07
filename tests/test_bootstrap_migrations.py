from scripts.bootstrap_migrations import (
    REVISION_ARC_NOTIFICATION,
    REVISION_BUDGETS,
    REVISION_MULTI_ROLE,
    detect_applied_revision,
    sanitize_database_url,
)


class FakeInspector:
    def __init__(self, tables=None, columns=None):
        self._tables = set(tables or [])
        self._columns = columns or {}

    def has_table(self, name: str) -> bool:
        return name in self._tables

    def get_columns(self, name: str):
        return [{"name": col} for col in self._columns.get(name, [])]

    def get_table_names(self):
        return list(self._tables)


def test_sanitize_database_url_strips_psql_wrapper_and_quotes():
    raw = "psql 'postgresql://user:pass@host:5432/hoa'"
    assert sanitize_database_url(raw) == "postgresql://user:pass@host:5432/hoa"


def test_detect_applied_revision_prefers_latest_sentinel():
    inspector = FakeInspector(
        tables={"user_roles", "budgets"},
        columns={"arc_requests": ["decision_notified_at"]},
    )

    revision, reason = detect_applied_revision(inspector)

    assert revision == REVISION_BUDGETS
    assert reason == "budgets table"


def test_detect_applied_revision_handles_arc_notification_column():
    inspector = FakeInspector(
        tables={"arc_requests"},
        columns={"arc_requests": ["decision_notified_at", "decision_notified_status"]},
    )

    revision, reason = detect_applied_revision(inspector)

    assert revision == REVISION_ARC_NOTIFICATION
    assert reason == "arc_requests.decision_notified_at"


def test_detect_applied_revision_handles_user_roles_table():
    inspector = FakeInspector(tables={"user_roles"})

    revision, reason = detect_applied_revision(inspector)

    assert revision == REVISION_MULTI_ROLE
    assert reason == "user_roles table"
