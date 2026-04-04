"""Integration test: verify PostgreSQL RLS prevents cross-tenant access.

Requires running PostgreSQL (docker compose up -d) with migrations applied.
Skip with: pytest -m "not integration"
"""

import os
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text

# Superuser (owns tables, runs migrations, bypasses RLS)
ADMIN_DB_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://jobapp:jobapp_dev@localhost:5432/jobapp",
)

# Non-superuser (API role, subject to RLS)
API_DB_URL = os.environ.get(
    "DATABASE_URL_API_SYNC",
    "postgresql://jobapp_api:jobapp_dev@localhost:5432/jobapp",
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def admin_engine():
    """Superuser engine — bypasses RLS. Used for setup/teardown."""
    eng = create_engine(ADMIN_DB_URL)
    yield eng
    eng.dispose()


@pytest.fixture(scope="module")
def api_engine():
    """Non-superuser engine — subject to RLS. Used for tenant-scoped queries."""
    eng = create_engine(API_DB_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def two_tenants(admin_engine):
    """Create two tenants and return their IDs (using superuser to bypass RLS)."""
    t1 = uuid.uuid4()
    t2 = uuid.uuid4()
    with admin_engine.connect() as conn:
        conn.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            [
                {"id": str(t1), "name": "Tenant A", "slug": f"tenant-a-{t1.hex[:8]}"},
                {"id": str(t2), "name": "Tenant B", "slug": f"tenant-b-{t2.hex[:8]}"},
            ],
        )
        conn.commit()
    yield str(t1), str(t2)
    # Cleanup using superuser
    with admin_engine.connect() as conn:
        conn.execute(text("DELETE FROM jobs WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1), "t2": str(t2)})
        conn.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"), {"t1": str(t1), "t2": str(t2)})
        conn.commit()


def test_rls_isolates_tenants(admin_engine, api_engine, two_tenants):
    """Tenant A cannot see Tenant B's jobs when using the API (non-superuser) role."""
    t1, t2 = two_tenants

    # Insert data as superuser (bypasses RLS)
    with admin_engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO jobs (tenant_id, url, url_hash, title, company) "
            "VALUES (:tid, :url, :hash, :title, :company)"
        ), [
            {"tid": t1, "url": "https://a.com/job1", "hash": "hash-a1", "title": "Job A", "company": "CompanyA"},
            {"tid": t2, "url": "https://b.com/job1", "hash": "hash-b1", "title": "Job B", "company": "CompanyB"},
        ])
        conn.commit()

    # Query as tenant A via API role — should only see Job A
    with api_engine.connect() as conn:
        conn.execute(text(f"SET app.current_tenant = '{t1}'"))
        rows = conn.execute(text("SELECT title FROM jobs")).fetchall()
        titles = [r[0] for r in rows]
        assert "Job A" in titles
        assert "Job B" not in titles

    # Query as tenant B via API role — should only see Job B
    with api_engine.connect() as conn:
        conn.execute(text(f"SET app.current_tenant = '{t2}'"))
        rows = conn.execute(text("SELECT title FROM jobs")).fetchall()
        titles = [r[0] for r in rows]
        assert "Job B" in titles
        assert "Job A" not in titles
