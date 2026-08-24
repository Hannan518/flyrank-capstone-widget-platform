"""add submissions, jobs, rate_limits; widgets.type check

Revision ID: 47ff713002d8
Revises: c2323fffff0d
Create Date: 2026-08-24 13:23:55.002395
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "47ff713002d8"
down_revision = "c2323fffff0d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limits",
        sa.Column("scope_key", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("scope_key", "window_start", name=op.f("pk_rate_limits")),
    )
    op.create_index(
        "ix_rate_window_start", "rate_limits", ["window_start"], unique=False
    )
    op.create_table(
        "submissions",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("widget_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("tenant_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["widget_id"], ["widgets.id"], name=op.f("fk_submissions_widget_id_widgets")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["users.id"], name=op.f("fk_submissions_tenant_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
    )
    op.create_index(
        "ix_sub_tenant_time",
        "submissions",
        ["tenant_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_sub_widget_time",
        "submissions",
        ["widget_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "uq_submissions_widget_idem",
        "submissions",
        ["widget_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("submission_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed_permanent')",
            name=op.f("ck_jobs_status"),
        ),
        sa.CheckConstraint(
            "type IN ('confirmation_email', 'webhook')", name=op.f("ck_jobs_type")
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["submissions.id"],
            name=op.f("fk_jobs_submission_id_submissions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index("ix_jobs_poll", "jobs", ["status", "next_attempt_at"], unique=False)
    op.create_check_constraint(
        op.f("ck_widgets_type"),
        "widgets",
        "type IN ('signup_form', 'cta', 'popover')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_widgets_type"), "widgets", type_="check")
    op.drop_index("ix_jobs_poll", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(
        "uq_submissions_widget_idem",
        table_name="submissions",
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.drop_index("ix_sub_widget_time", table_name="submissions")
    op.drop_index("ix_sub_tenant_time", table_name="submissions")
    op.drop_table("submissions")
    op.drop_index("ix_rate_window_start", table_name="rate_limits")
    op.drop_table("rate_limits")
