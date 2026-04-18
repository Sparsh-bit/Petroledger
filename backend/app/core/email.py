"""PetroLedger — Email service for invites, password resets, and shift notifications."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_ROLE_PORTAL: dict[str, str] = {
    "admin": "FRONTEND_ADMIN_URL",
    "manager": "FRONTEND_MANAGER_URL",
    "worker": "FRONTEND_WORKER_URL",
    "owner": "FRONTEND_OWNER_URL",
}


def _send_sync(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> None:
    """Low-level sync SMTP send. Falls back to logging if SMTP_HOST is blank."""
    settings = get_settings()
    if not settings.SMTP_HOST:
        logger.info(
            "SMTP not configured — email not sent [to=%s subject=%s]",
            to_email,
            subject,
        )
        return

    from_addr = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(from_addr, [to_email], msg.as_string())
        server.quit()
        logger.info("Email sent to %s [subject=%s]", to_email, subject)
    except Exception:
        logger.exception("Failed to send email to %s [subject=%s]", to_email, subject)


async def send_email(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    """Async wrapper — offloads the blocking SMTP conversation to a thread pool."""
    await asyncio.to_thread(
        _send_sync,
        to_email=to,
        subject=subject,
        text_body=text_body or _html_to_text(html_body),
        html_body=html_body,
    )


def _html_to_text(html: str) -> str:
    """Crude HTML→text fallback for clients that prefer plain text."""
    import re
    stripped = re.sub(r"<[^>]+>", "", html)
    return re.sub(r"\s+", " ", stripped).strip()


def send_password_reset_email(to_email: str, full_name: str, reset_url: str) -> None:
    """Send the password-reset email (sync call site — wraps `_send_sync`)."""
    subject = "Reset your PetroLedger password"
    text_body = (
        f"Hi {full_name},\n\n"
        f"We received a request to reset your PetroLedger password. "
        f"Open the link below within 24 hours to choose a new password:\n\n"
        f"{reset_url}\n\n"
        f"If you didn't request this, you can safely ignore this email — "
        f"your password will stay the same.\n\n"
        f"— PetroLedger Team"
    )
    html_body = f"""
<html>
<body style="font-family:Arial,sans-serif;color:#1f2937;max-width:520px;margin:auto;padding:24px;">
  <h2 style="color:#f97316;">Reset your password</h2>
  <p>Hi <strong>{full_name}</strong>,</p>
  <p>We received a request to reset your PetroLedger password.</p>
  <p><a href="{reset_url}" style="display:inline-block;background:#f97316;color:#fff;padding:12px 20px;border-radius:6px;text-decoration:none;">Choose a new password</a></p>
  <p style="color:#6b7280;font-size:13px;">This link is valid for 24 hours. If you didn't request a reset, no action is needed.</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
  <p style="font-size:12px;color:#6b7280;">— PetroLedger Team</p>
</body>
</html>
"""
    _send_sync(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_invite_email(
    *,
    to_email: str,
    full_name: str,
    role: str,
    temporary_password: str,
) -> None:
    """Send an invite email to a newly created team member.

    Falls back to console logging when ``SMTP_HOST`` is blank so local dev
    never needs real SMTP credentials.
    """
    settings = get_settings()
    portal_attr = _ROLE_PORTAL.get(role.lower(), "FRONTEND_OWNER_URL")
    login_url = getattr(settings, portal_attr)

    subject = f"You've been invited to PetroLedger as {role.title()}"

    text_body = (
        f"Hi {full_name},\n\n"
        f"You have been invited to PetroLedger as a {role.title()}.\n\n"
        f"Login URL : {login_url}\n"
        f"Email     : {to_email}\n"
        f"Password  : {temporary_password}\n\n"
        f"Please log in and change your password immediately.\n"
        f"This invite is valid for {settings.INVITE_EXPIRY_HOURS} hours.\n\n"
        f"— PetroLedger Team"
    )

    html_body = f"""
<html>
<body style="font-family:Arial,sans-serif;color:#1f2937;max-width:520px;margin:auto;padding:24px;">
  <h2 style="color:#f97316;">Welcome to PetroLedger!</h2>
  <p>Hi <strong>{full_name}</strong>,</p>
  <p>You've been invited to join as a <strong>{role.title()}</strong>.</p>
  <table style="border-collapse:collapse;width:100%;margin:16px 0;">
    <tr>
      <td style="padding:8px 12px;background:#fff7ed;border:1px solid #fed7aa;font-weight:600;">Login URL</td>
      <td style="padding:8px 12px;border:1px solid #e5e7eb;">
        <a href="{login_url}" style="color:#f97316;">{login_url}</a>
      </td>
    </tr>
    <tr>
      <td style="padding:8px 12px;background:#fff7ed;border:1px solid #fed7aa;font-weight:600;">Email</td>
      <td style="padding:8px 12px;border:1px solid #e5e7eb;">{to_email}</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;background:#fff7ed;border:1px solid #fed7aa;font-weight:600;">Temporary Password</td>
      <td style="padding:8px 12px;border:1px solid #e5e7eb;font-family:monospace;letter-spacing:1px;">{temporary_password}</td>
    </tr>
  </table>
  <p style="color:#dc2626;font-size:13px;">
    Please change your password immediately after logging in.<br>
    This invite expires in <strong>{settings.INVITE_EXPIRY_HOURS} hours</strong>.
  </p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
  <p style="font-size:12px;color:#6b7280;">— PetroLedger Team</p>
</body>
</html>
"""

    if not settings.SMTP_HOST:
        logger.info(
            "SMTP not configured — invite details [to=%s role=%s login=%s password=%s]",
            to_email,
            role,
            login_url,
            temporary_password,
        )
        return

    from_addr = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)

        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(from_addr, [to_email], msg.as_string())
        server.quit()
        logger.info("Invite email sent to %s", to_email)
    except Exception:
        logger.exception("Failed to send invite email to %s — user was still created", to_email)
