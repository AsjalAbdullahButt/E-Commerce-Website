import base64
from dataclasses import dataclass
from typing import Optional, Sequence

import httpx

from config import settings
from utils.logger import get_logger, log_to_db

logger = get_logger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    mime_type: str = "application/pdf"


class EmailService:
    """Transactional email via SendGrid's REST API. Never raises — a failed/unconfigured send
    must not break the request that triggered it, same contract as utils/logger.py::log_to_db.
    When SendGrid isn't configured, falls back to logging the email's content so every flow
    that sends mail (password reset, order confirmation, ...) stays fully exercisable in local
    dev without a real account."""

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.sendgrid_enabled and settings.sendgrid_api_key and settings.sendgrid_from_email)

    @staticmethod
    async def send(
        to_email: str, subject: str, html_body: str, *, event_code: str, meta: Optional[dict] = None,
        attachments: Optional[Sequence[EmailAttachment]] = None,
    ) -> bool:
        meta = meta or {}
        attachments = attachments or []

        if not EmailService.is_configured():
            attachment_note = f" (+{len(attachments)} attachment(s): {', '.join(a.filename for a in attachments)})" if attachments else ""
            logger.info(f"[DEV EMAIL] To: {to_email} | Subject: {subject}{attachment_note}\n{html_body}")
            await log_to_db(
                event_code, __name__, f"email not sent (SendGrid not configured): {subject} -> {to_email}",
                {"to": to_email, "subject": subject, "attachments": [a.filename for a in attachments], **meta},
            )
            return False

        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": settings.sendgrid_from_email, "name": settings.sendgrid_from_name},
            "subject": subject,
            "content": [{"type": "text/html", "value": html_body}],
        }
        if attachments:
            payload["attachments"] = [
                {
                    "content": base64.b64encode(a.content).decode("ascii"),
                    "filename": a.filename,
                    "type": a.mime_type,
                    "disposition": "attachment",
                }
                for a in attachments
            ]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    SENDGRID_API_URL, json=payload,
                    headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
                )
            if resp.status_code >= 400:
                await log_to_db(
                    "EMAIL_SEND_FAILED", __name__, f"SendGrid rejected email to {to_email}: {resp.status_code}",
                    {"to": to_email, "subject": subject, "status": resp.status_code, "body": resp.text[:500], **meta},
                )
                logger.error(f"SendGrid rejected email to {to_email}: {resp.status_code} {resp.text[:200]}")
                return False

            await log_to_db(event_code, __name__, f"email sent: {subject} -> {to_email}", {"to": to_email, "subject": subject, **meta})
            return True
        except Exception as e:
            await log_to_db(
                "EMAIL_SEND_ERROR", __name__, f"failed to send email to {to_email}: {e}",
                {"to": to_email, "subject": subject, "error": str(e), **meta},
            )
            logger.error(f"Email send error: {e}")
            return False
