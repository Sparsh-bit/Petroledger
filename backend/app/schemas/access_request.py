"""PetroLedger — Access Request schemas."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

PumpRange = Literal["1", "2-5", "6-10", "11-25", "25+"]
StatusLiteral = Literal["NEW", "CONTACTED", "APPROVED", "REJECTED"]

_PHONE_RE = re.compile(r"^\+91[\s-]?[6-9]\d{9}$")


class AccessRequestCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=32)
    company: str = Field(min_length=1, max_length=255)
    pump_count_range: PumpRange
    city: str = Field(min_length=1, max_length=128)
    state: str = Field(min_length=1, max_length=128)
    message: str | None = Field(default=None, max_length=10_000)
    consent: bool = Field(default=False)

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        cleaned = v.strip().replace(" ", "").replace("-", "")
        # Normalize to "+91XXXXXXXXXX" form for validation
        candidate = cleaned
        if not candidate.startswith("+"):
            candidate = "+91" + candidate.lstrip("0")
        if not re.match(r"^\+91[6-9]\d{9}$", candidate):
            raise ValueError(
                "Phone must be a valid Indian mobile number (+91 followed by 10 digits starting with 6-9)."
            )
        return candidate

    @field_validator("consent")
    @classmethod
    def _check_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must agree to be contacted.")
        return v


class AccessRequestUpdate(BaseModel):
    status: StatusLiteral | None = None
    provider_notes: str | None = Field(default=None, max_length=20_000)


class AccessRequestResponse(BaseModel):
    id: str
    full_name: str
    email: str
    phone: str
    company: str
    pump_count_range: str
    city: str
    state: str
    message: str | None
    status: str
    provider_notes: str | None
    created_at: datetime
    updated_at: datetime


class AccessRequestSubmitResponse(BaseModel):
    id: str
    status: str
    message: str


class AccessRequestList(BaseModel):
    items: list[AccessRequestResponse]
    total: int
    page: int
    page_size: int


class AccessRequestStats(BaseModel):
    new: int
    contacted: int
    approved: int
    rejected: int
    total: int
