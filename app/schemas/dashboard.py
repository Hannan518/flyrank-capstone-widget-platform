from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class WidgetConfig(BaseModel):
    type: str
    title: str
    description: str | None
    fields: list[dict[str, Any]]
    button_text: str
    display_options: dict[str, Any]


class SubmissionOut(BaseModel):
    id: UUID
    widget_id: UUID
    payload: dict[str, Any]
    idempotency_key: str | None
    country: str | None
    city: str | None
    region: str | None
    latitude: float | None
    longitude: float | None
    ip_address: str
    user_agent: str | None
    created_at: datetime

    @classmethod
    def from_row(cls, row) -> "SubmissionOut":
        return cls(
            id=row.id,
            widget_id=row.widget_id,
            payload=dict(row.payload),
            idempotency_key=row.idempotency_key,
            country=row.country,
            city=row.city,
            region=row.region,
            latitude=row.latitude,
            longitude=row.longitude,
            ip_address=str(row.ip_address),
            user_agent=row.user_agent,
            created_at=row.created_at,
        )


class SubmissionsPage(BaseModel):
    items: list[SubmissionOut]
    next_cursor: str | None = None


class PerWidgetStat(BaseModel):
    widget_id: UUID
    title: str
    count: int


class TimeseriesPoint(BaseModel):
    day: date
    count: int


class GeoStat(BaseModel):
    country: str
    count: int


class StatsOut(BaseModel):
    total: int
    per_widget: list[PerWidgetStat]
    timeseries: list[TimeseriesPoint]
    geo: list[GeoStat]
