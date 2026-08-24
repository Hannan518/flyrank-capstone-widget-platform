"""create users and widgets

Revision ID: c2323fffff0d
Revises:
Create Date: 2026-08-24 12:51:22.455323
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c2323fffff0d"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_table(
        "widgets",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("owner_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("button_text", sa.String(length=60), nullable=False),
        sa.Column(
            "display_options", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("allowed_origins", postgresql.ARRAY(sa.Text()), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_widgets_owner_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_widgets")),
    )
    op.create_index(
        op.f("ix_widgets_owner_id"), "widgets", ["owner_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_widgets_owner_id"), table_name="widgets")
    op.drop_table("widgets")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
