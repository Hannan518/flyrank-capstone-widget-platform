from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SubmissionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    widget_id: UUID
    fields: dict[str, str] = Field(default_factory=dict)
    website: str = Field(default="", max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=64)

    @field_validator("idempotency_key")
    @classmethod
    def _validate_key(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        try:
            UUID(value)
        except ValueError:
            raise ValueError("idempotency_key must be a UUID")
        return value

    @field_validator("fields")
    @classmethod
    def _bound_values(cls, value: dict[str, str]) -> dict[str, str]:
        for name, content in value.items():
            if len(content) > 2000:
                raise ValueError(f"field {name!r} exceeds 2000 characters")
        return value
