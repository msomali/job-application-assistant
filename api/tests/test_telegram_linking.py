"""Test Telegram account linking logic."""

from src.db.models import NotificationPreference, TelegramAccount, TelegramLinkCode


def test_telegram_account_model():
    """Verify TelegramAccount model has required fields."""
    cols = {c.name for c in TelegramAccount.__table__.columns}
    assert "chat_id" in cols
    assert "user_id" in cols
    assert "tenant_id" in cols
    assert "is_active" in cols


def test_link_code_model():
    """Verify TelegramLinkCode model has required fields."""
    cols = {c.name for c in TelegramLinkCode.__table__.columns}
    assert "code" in cols
    assert "user_id" in cols
    assert "expires_at" in cols


def test_notification_preference_model():
    """Verify NotificationPreference model has required fields."""
    cols = {c.name for c in NotificationPreference.__table__.columns}
    assert "telegram_enabled" in cols
    assert "user_id" in cols
