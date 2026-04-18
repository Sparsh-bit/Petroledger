"""PetroLedger — Public Contact Form Routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.contact_submission import ContactSubmission

router = APIRouter()


class ContactSubmissionPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    company: str | None = Field(default=None, max_length=255)
    message: str = Field(min_length=1, max_length=10_000)


class ContactSubmissionResponse(BaseModel):
    id: str
    message: str


@router.post(
    "",
    response_model=ContactSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a contact-form message",
)
@limiter.limit("10/hour")
async def submit_contact(
    request: Request,
    payload: ContactSubmissionPayload,
    db: AsyncSession = Depends(get_db),
) -> ContactSubmissionResponse:
    submission = ContactSubmission(
        name=payload.name.strip(),
        email=str(payload.email).lower(),
        company=(payload.company or "").strip() or None,
        message=payload.message.strip(),
        ip_address=(request.client.host if request.client else None),
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return ContactSubmissionResponse(
        id=str(submission.id),
        message="Thanks — we'll be in touch within one business day.",
    )
