from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

WIDGET_BUNDLE_VERSION = 1

_ORIGIN_PATTERN = r"^https?://[a-zA-Z0-9._-]+(:[0-9]{1,5})?$"


class FieldDef(BaseModel):
    name: str = Field(pattern=r"^[a-z_][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=120)
    type: Literal["text", "email", "textarea"] = "text"
    required: bool = False


class WidgetCreate(BaseModel):
    model_config = {"extra": "forbid"}

    type: Literal["signup_form", "cta", "popover"]
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    fields: list[FieldDef] = Field(default_factory=list, max_length=20)
    button_text: str = Field(default="Submit", min_length=1, max_length=60)
    display_options: dict[str, Any] = Field(default_factory=dict)
    allowed_origins: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("allowed_origins")
    @classmethod
    def _validate_origins(cls, value: list[str]) -> list[str]:
        import re

        for origin in value:
            if not re.match(_ORIGIN_PATTERN, origin):
                raise ValueError(f"invalid origin: {origin}")
        return [o.rstrip("/") for o in value]


class WidgetUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    fields: list[FieldDef] | None = Field(default=None, max_length=20)
    button_text: str | None = Field(default=None, min_length=1, max_length=60)
    display_options: dict[str, Any] | None = None
    allowed_origins: list[str] | None = Field(default=None, max_length=20)

    @field_validator("allowed_origins")
    @classmethod
    def _validate_origins(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        import re

        for origin in value:
            if not re.match(_ORIGIN_PATTERN, origin):
                raise ValueError(f"invalid origin: {origin}")
        return [o.rstrip("/") for o in value]


class WidgetOut(BaseModel):
    id: UUID
    type: str
    title: str
    description: str | None
    fields: list[dict[str, Any]]
    button_text: str
    display_options: dict[str, Any]
    allowed_origins: list[str]
    created_at: datetime
    updated_at: datetime
    embed_snippet: str

    @classmethod
    def from_widget(cls, widget) -> "WidgetOut":
        from app.core.config import get_settings

        settings = get_settings()
        snippet = (
            f'<script src="{settings.public_base_url}'
            f"/widget.v{WIDGET_BUNDLE_VERSION}.js?id={widget.id}\"></script>"
        )
        return cls(
            id=widget.id,
            type=widget.type,
            title=widget.title,
            description=widget.description,
            fields=list(widget.fields),
            button_text=widget.button_text,
            display_options=dict(widget.display_options),
            allowed_origins=list(widget.allowed_origins),
            created_at=widget.created_at,
            updated_at=widget.updated_at,
            embed_snippet=snippet,
        )
