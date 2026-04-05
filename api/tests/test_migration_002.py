"""Verify Phase 4 ORM models are importable and have correct columns."""

from src.db.models import NotificationPreference, TelegramAccount, TelegramLinkCode, Task


def test_telegram_account_columns():
    cols = {c.name for c in TelegramAccount.__table__.columns}
    assert {"id", "tenant_id", "user_id", "chat_id", "username", "is_active", "linked_at"} <= cols


def test_telegram_link_code_columns():
    cols = {c.name for c in TelegramLinkCode.__table__.columns}
    assert {"id", "user_id", "code", "expires_at"} <= cols


def test_notification_preference_columns():
    cols = {c.name for c in NotificationPreference.__table__.columns}
    assert {"id", "tenant_id", "user_id", "telegram_enabled"} <= cols


def test_task_has_user_id():
    cols = {c.name for c in Task.__table__.columns}
    assert "user_id" in cols
