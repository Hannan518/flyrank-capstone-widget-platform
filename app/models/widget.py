from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

WIDGET_TYPES = ("signup_form", "cta", "popover")


class Widget(Base):
    __tablename__ = "widgets"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    button_text: Mapped[str] = mapped_column(String(60), nullable=False, default="Submit")
    display_options: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    allowed_origins: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
