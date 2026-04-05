"""Phase 4: Telegram accounts, link codes, notification prefs, task user_id.

Revision ID: 002
Revises: 001
Create Date: 2026-04-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_RLS_TABLES = ["telegram_accounts", "notification_preferences"]


def upgrade() -> None:
    # --- telegram_accounts ---
    op.create_table(
        "telegram_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chat_id", sa.BigInteger, unique=True, nullable=False),
        sa.Column("username", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- telegram_link_codes (no RLS) ---
    op.create_table(
        "telegram_link_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code", sa.Text, unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    # --- notification_preferences ---
    op.create_table(
        "notification_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("telegram_enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- Add user_id to tasks ---
    op.add_column("tasks", sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))

    # --- Grant privileges to API role ---
    for table in ["telegram_accounts", "telegram_link_codes", "notification_preferences"]:
        op.execute(f"GRANT ALL PRIVILEGES ON {table} TO jobapp_api")

    # --- RLS on new tenant-scoped tables ---
    for table in NEW_RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
        op.execute(
            f"CREATE POLICY tenant_insert ON {table} "
            f"FOR INSERT WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )


def downgrade() -> None:
    for table in reversed(NEW_RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_column("tasks", "user_id")
    op.drop_table("notification_preferences")
    op.drop_table("telegram_link_codes")
    op.drop_table("telegram_accounts")
